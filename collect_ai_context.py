#!/usr/bin/env python3
"""
collect_ai_context.py
---------------------
Collects AI coding assistant context files from your machine and packages
them into a ZIP file ready to paste into ChatGPT / Codex / any LLM.

Supports: Claude Code, Cursor, GitHub Copilot, Cline, Continue, Aider, Windsurf

Usage:
    python collect_ai_context.py                        # scans current dir + home
    python collect_ai_context.py --project /path/to/proj
    python collect_ai_context.py --output my_bundle.zip
    python collect_ai_context.py --txt                  # also writes a plain .txt bundle
    python collect_ai_context.py --depth 5              # max folder scan depth (default 4)
"""

import argparse
import json
import os
import platform
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Config: files and patterns to collect
# ---------------------------------------------------------------------------

# Exact filenames (case-insensitive match)
TARGET_FILENAMES = {
    # Claude Code
    "claude.md",
    "claude.local.md",
    # Cursor
    ".cursorrules",
    "cursor_rules.md",
    # GitHub Copilot
    ".github/copilot-instructions.md",
    # Cline / Continue / Aider / Windsurf
    ".clinerules",
    ".continuerules",
    ".aider.conf.yml",
    ".aider.model.settings.yml",
    ".windsurfrules",
    # Generic project context
    "readme.md",
    "requirements.txt",
    "requirements-dev.txt",
    "pyproject.toml",
    "setup.cfg",
    "setup.py",
    "package.json",
    "pom.xml",
    "build.gradle",
    "cargo.toml",
    "go.mod",
    ".env.example",
    ".env.template",
    "dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
}

# Directories to scan for config files (relative to project root)
# These are scanned shallowly — SKIP_DIRS still applies inside them
TARGET_DIRS = {
    ".cursor/rules",
    ".cursor/prompts",
    ".github",
    ".continue",
    ".cline",
    # NOTE: .claude is intentionally excluded from TARGET_DIRS because it
    # contains large internal state (debug logs, file-history, cache).
    # CLAUDE.md inside .claude/ is caught by TARGET_FILENAMES scan instead.
}

# Global config: specific files/subdirs within home to collect (not whole dirs)
# Format: (home_relative_path, is_dir)  — dirs are scanned 1 level deep only
HOME_CONFIG_TARGETS = [
    # Claude Code — only settings/instructions files, not logs or history
    (Path(".claude/CLAUDE.md"), False),
    (Path(".claude/settings.json"), False),
    (Path(".claude/settings.local.json"), False),
    (Path(".claude/projects"), True),       # CLAUDE.md files per project
    # Cursor global rules
    (Path(".cursor/rules"), True),
    (Path(".cursorrules"), False),
    # Aider
    (Path(".aider.conf.yml"), False),
    (Path(".config/aider/aider.conf.yml"), False),
    # Continue
    (Path(".continue/config.json"), False),
    (Path(".continue/config.yaml"), False),
]

# Extensions that are safe to read as text
TEXT_EXTENSIONS = {
    ".md", ".txt", ".yml", ".yaml", ".toml", ".cfg", ".ini",
    ".json", ".env", ".conf", ".properties", ".xml", ".gradle",
    ".mod", ".sum",
}

SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "env",
    "dist", "build", ".tox", ".mypy_cache", ".pytest_cache",
    "site-packages", ".idea", ".vscode", "target",
    # Cursor / Claude internals — skip large noise dirs
    "extensions", "logs", "cache", "debug", "file-history",
    "projects", "conversations", "workspaces", "tmp", "temp",
    "CachedData", "User", "History", "GPUCache", "Crashpad",
}

MAX_FILE_SIZE_BYTES = 512 * 1024  # 512 KB per file

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def log(msg: str):
    print(f"  {msg}")


def is_text_file(path: Path) -> bool:
    return path.suffix.lower() in TEXT_EXTENSIONS or path.suffix == ""


def safe_read(path: Path) -> str | None:
    try:
        if path.stat().st_size > MAX_FILE_SIZE_BYTES:
            return f"[SKIPPED — file too large: {path.stat().st_size // 1024} KB]"
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"[ERROR reading file: {e}]"


def get_project_tree(root: Path, max_depth: int = 3) -> str:
    """Build a simple directory tree string."""
    lines = [str(root)]

    def _walk(path: Path, prefix: str, depth: int):
        if depth > max_depth:
            return
        try:
            entries = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        except PermissionError:
            return
        entries = [e for e in entries if e.name not in SKIP_DIRS]
        for i, entry in enumerate(entries):
            connector = "└── " if i == len(entries) - 1 else "├── "
            lines.append(f"{prefix}{connector}{entry.name}")
            if entry.is_dir():
                extension = "    " if i == len(entries) - 1 else "│   "
                _walk(entry, prefix + extension, depth + 1)

    _walk(root, "", 0)
    return "\n".join(lines)


def get_git_info(root: Path) -> dict:
    info = {}
    try:
        info["branch"] = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=root, stderr=subprocess.DEVNULL, text=True
        ).strip()
        info["last_commit"] = subprocess.check_output(
            ["git", "log", "-1", "--oneline"],
            cwd=root, stderr=subprocess.DEVNULL, text=True
        ).strip()
        info["remote"] = subprocess.check_output(
            ["git", "remote", "get-url", "origin"],
            cwd=root, stderr=subprocess.DEVNULL, text=True
        ).strip()
    except Exception:
        pass
    return info


# ---------------------------------------------------------------------------
# Collection logic
# ---------------------------------------------------------------------------

def collect_project_files(root: Path, max_depth: int) -> dict[str, str]:
    """Walk project directory and collect matching files."""
    collected: dict[str, str] = {}

    # 1. Scan for exact filename matches up to max_depth
    def _scan(path: Path, depth: int):
        if depth > max_depth:
            return
        try:
            for entry in path.iterdir():
                if entry.is_dir():
                    if entry.name.lower() not in SKIP_DIRS:
                        _scan(entry, depth + 1)
                elif entry.is_file():
                    rel = entry.relative_to(root)
                    name_lower = entry.name.lower()
                    rel_lower = str(rel).lower().replace("\\", "/")
                    if name_lower in TARGET_FILENAMES or rel_lower in TARGET_FILENAMES:
                        if is_text_file(entry):
                            content = safe_read(entry)
                            if content is not None:
                                collected[str(rel)] = content
                                log(f"[project] {rel}")
        except PermissionError:
            pass

    _scan(root, 0)

    # 2. Collect files inside target dirs (respecting SKIP_DIRS)
    for target_dir in TARGET_DIRS:
        dir_path = root / target_dir
        if not (dir_path.exists() and dir_path.is_dir()):
            continue
        for entry in dir_path.rglob("*"):
            if not entry.is_file():
                continue
            # Skip if any parent part is in SKIP_DIRS
            rel_parts = entry.relative_to(dir_path).parts
            if any(p.lower() in SKIP_DIRS for p in rel_parts):
                continue
            if is_text_file(entry):
                rel = entry.relative_to(root)
                if str(rel) not in collected:
                    content = safe_read(entry)
                    if content is not None:
                        collected[str(rel)] = content
                        log(f"[project] {rel}")

    return collected


def collect_home_files(home: Path) -> dict[str, str]:
    """Collect targeted global AI config files from the user's home directory."""
    collected: dict[str, str] = {}

    for target, is_dir in HOME_CONFIG_TARGETS:
        full_path = home / target
        if not full_path.exists():
            continue

        if not is_dir:
            # Single file
            if full_path.is_file() and is_text_file(full_path):
                content = safe_read(full_path)
                if content is not None:
                    label = f"[HOME]/{target}"
                    collected[label] = content
                    log(f"[home]    {target}")
        else:
            # Directory — scan for CLAUDE.md / config files, max 3 levels deep
            for entry in full_path.rglob("*"):
                if not entry.is_file():
                    continue
                # Skip noisy internal subdirs
                parts = entry.relative_to(full_path).parts
                if any(p.lower() in SKIP_DIRS for p in parts):
                    continue
                name_lower = entry.name.lower()
                # Only grab real AI context files, not every file
                if name_lower in TARGET_FILENAMES or entry.suffix.lower() in {".md", ".json", ".yml", ".yaml"}:
                    # Skip obviously noisy JSON files (large IDE state files)
                    if entry.stat().st_size > 50 * 1024:
                        continue
                    content = safe_read(entry)
                    if content is not None:
                        rel = entry.relative_to(home)
                        label = f"[HOME]/{rel}"
                        collected[label] = content
                        log(f"[home]    {rel}")

    return collected


def build_manifest(
    project_root: Path,
    project_files: dict,
    home_files: dict,
    git_info: dict,
) -> str:
    """Build the top-level MANIFEST.txt describing the bundle."""
    lines = [
        "=" * 70,
        "  AI CONTEXT BUNDLE",
        f"  Generated : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"  Machine   : {platform.node()} ({platform.system()} {platform.release()})",
        f"  Python    : {sys.version.split()[0]}",
        f"  Project   : {project_root}",
    ]
    if git_info:
        lines += [
            f"  Git branch: {git_info.get('branch', 'n/a')}",
            f"  Last commit: {git_info.get('last_commit', 'n/a')}",
            f"  Remote    : {git_info.get('remote', 'n/a')}",
        ]
    lines += [
        "=" * 70,
        "",
        f"PROJECT FILES ({len(project_files)}):",
    ]
    for f in sorted(project_files):
        lines.append(f"  • {f}")
    lines += [
        "",
        f"HOME / GLOBAL CONFIG FILES ({len(home_files)}):",
    ]
    for f in sorted(home_files):
        lines.append(f"  • {f}")
    lines += [
        "",
        "HOW TO USE THIS BUNDLE:",
        "  1. Open the txt_bundle.txt (or individual files) from this ZIP.",
        "  2. Paste the contents as the SYSTEM PROMPT in ChatGPT / Codex.",
        "  3. Then describe your task.",
        "",
        "QUICK PASTE TEMPLATE:",
        "  'You are a coding assistant. Here is the full project context:",
        "   [PASTE txt_bundle.txt HERE]",
        "   Now help me with: <your task>'",
        "=" * 70,
    ]
    return "\n".join(lines)


def build_txt_bundle(
    project_files: dict,
    home_files: dict,
    project_root: Path,
    tree: str,
) -> str:
    """Combine everything into a single plain-text file for easy pasting."""
    sections = []
    sep = "\n" + "=" * 70 + "\n"

    sections.append(
        f"=== AI CONTEXT BUNDLE — {datetime.now().strftime('%Y-%m-%d %H:%M')} ===\n"
        f"Project: {project_root}"
    )
    sections.append(f"=== PROJECT DIRECTORY TREE ===\n{tree}")

    for filename, content in sorted(project_files.items()):
        sections.append(f"=== FILE: {filename} ===\n{content}")

    for filename, content in sorted(home_files.items()):
        sections.append(f"=== GLOBAL CONFIG: {filename} ===\n{content}")

    return sep.join(sections)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Collect AI coding context files into a ZIP bundle."
    )
    parser.add_argument(
        "--project", "-p",
        default=".",
        help="Project root directory to scan (default: current directory)",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output ZIP filename (default: ai_context_<timestamp>.zip)",
    )
    parser.add_argument(
        "--txt", "-t",
        action="store_true",
        help="Also write a plain-text bundle (txt_bundle.txt) inside the ZIP",
    )
    parser.add_argument(
        "--depth", "-d",
        type=int,
        default=4,
        help="Max directory scan depth for project files (default: 4)",
    )
    parser.add_argument(
        "--no-home",
        action="store_true",
        help="Skip scanning home directory global config files",
    )
    parser.add_argument(
        "--no-tree",
        action="store_true",
        help="Skip generating project directory tree",
    )
    args = parser.parse_args()

    project_root = Path(args.project).resolve()
    home = Path.home()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_zip = Path(args.output) if args.output else Path(f"ai_context_{timestamp}.zip")

    print(f"\n{'='*60}")
    print(f"  AI Context Collector")
    print(f"  Project : {project_root}")
    print(f"  Output  : {output_zip}")
    print(f"{'='*60}\n")

    # Collect files
    print("Scanning project files...")
    project_files = collect_project_files(project_root, args.depth)

    home_files: dict[str, str] = {}
    if not args.no_home:
        print("\nScanning global AI config files (home directory)...")
        home_files = collect_home_files(home)

    # Project tree
    tree = ""
    if not args.no_tree:
        print("\nBuilding project tree...")
        tree = get_project_tree(project_root, max_depth=3)

    # Git info
    git_info = get_git_info(project_root)

    # Build manifest
    manifest = build_manifest(project_root, project_files, home_files, git_info)

    # Write ZIP
    print(f"\nPackaging into {output_zip}...")
    with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:

        # MANIFEST
        zf.writestr("MANIFEST.txt", manifest)

        # Project tree
        if tree:
            zf.writestr("project_tree.txt", tree)

        # Git info
        if git_info:
            zf.writestr("git_info.json", json.dumps(git_info, indent=2))

        # Project files
        for filename, content in project_files.items():
            arc_name = f"project/{filename.replace(os.sep, '/')}"
            zf.writestr(arc_name, content)

        # Home/global config files
        for filename, content in home_files.items():
            safe_name = filename.replace("[HOME]/", "").replace("\\", "/")
            arc_name = f"global_config/{safe_name}"
            zf.writestr(arc_name, content)

        # Optional: single txt bundle for easy paste
        if args.txt or True:  # always include for convenience
            txt = build_txt_bundle(project_files, home_files, project_root, tree)
            zf.writestr("txt_bundle.txt", txt)

    # Summary
    size_kb = output_zip.stat().st_size / 1024
    total_files = len(project_files) + len(home_files)
    print(f"\n{'='*60}")
    print(f"  Done!")
    print(f"  Files collected : {total_files}")
    print(f"  ZIP size        : {size_kb:.1f} KB")
    print(f"  Output          : {output_zip.resolve()}")
    print(f"{'='*60}")
    print(f"\nNext steps:")
    print(f"  1. Unzip and open  txt_bundle.txt")
    print(f"  2. Paste into ChatGPT/Codex as your system prompt")
    print(f"  3. Add your task at the end\n")


if __name__ == "__main__":
    main()
