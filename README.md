# AI Context Collector

A zero-dependency Python script that collects all your AI coding assistant context files — from Claude Code, Cursor, Aider, Continue, GitHub Copilot, and more — and packages them into a single ZIP bundle ready to paste into **ChatGPT**, **OpenAI Codex**, or any other LLM.

**Use case:** Hit Claude Code or Cursor API rate limits? Export your full project context and skill instructions, then continue working in ChatGPT/Codex with full context parity. Without wasting tokens.

---

## Get the Script

**Windows (Command Prompt or PowerShell):**
```cmd
curl -L https://raw.githubusercontent.com/dataamigos/ai-context-collector/master/collect_ai_context.py -o collect_ai_context.py
```

**Mac / Linux (Terminal):**
```bash
curl -sL https://raw.githubusercontent.com/dataamigos/ai-context-collector/master/collect_ai_context.py -o collect_ai_context.py
```

Or just **download directly**: [collect_ai_context.py](https://raw.githubusercontent.com/dataamigos/ai-context-collector/master/collect_ai_context.py) → right-click → Save As

---

## Features

- Collects `CLAUDE.md`, `.cursorrules`, `.cursor/rules/`, `MEMORY.md`, `README.md`, `requirements.txt`, `pyproject.toml`, `Dockerfile`, and more
- Picks up **global AI config** from your home directory (`~/.claude/`, `~/.cursor/rules/`, etc.)
- Generates a **single `txt_bundle.txt`** for easy copy-paste into any LLM chat
- Includes a project directory tree and git metadata
- Smart noise filtering — skips `node_modules`, build artifacts, editor internals, logs, and debug dirs
- Zero dependencies — pure Python 3.10+ stdlib
- Works on **Windows, Mac, and Linux**

---

## Supported Tools

| Tool | Files Collected |
|------|----------------|
| Claude Code | `CLAUDE.md`, `settings.json`, per-project `MEMORY.md` |
| Cursor | `.cursorrules`, `.cursor/rules/*.md` |
| GitHub Copilot | `.github/copilot-instructions.md` |
| Aider | `.aider.conf.yml` |
| Continue | `.continue/config.json` / `.yaml` |
| Cline / Windsurf | `.clinerules`, `.windsurfrules` |
| Any project | `README.md`, `requirements.txt`, `pyproject.toml`, `package.json`, `Dockerfile`, `docker-compose.yml`, etc. |

---

## Usage

```bash
# Basic — scan current directory
python collect_ai_context.py

# Scan a specific project
python collect_ai_context.py --project /path/to/your-project

# Custom output filename
python collect_ai_context.py -p ./my-project -o codex_bundle.zip

# Skip home directory global config
python collect_ai_context.py --no-home

# Limit scan depth (useful for large monorepos)
python collect_ai_context.py --depth 2

# Skip project directory tree generation
python collect_ai_context.py --no-tree
```

### All Options

```
--project / -p   Project directory to scan (default: current directory)
--output  / -o   ZIP output filename (default: ai_context_<timestamp>.zip)
--depth   / -d   Max folder scan depth (default: 4)
--no-home        Skip scanning ~/.claude, ~/.cursor, etc.
--no-tree        Skip generating the project directory tree
```

---

## Output ZIP Structure

```
ai_context_20260312_134500.zip
├── MANIFEST.txt              ← Summary: what was collected, git info, usage guide
├── project_tree.txt          ← Directory tree of your project
├── git_info.json             ← Branch, last commit, remote URL
├── txt_bundle.txt            ← ★ Single file to paste into ChatGPT/Codex
├── project/
│   ├── CLAUDE.md
│   ├── README.md
│   ├── requirements.txt
│   ├── pyproject.toml
│   └── .cursor/rules/...
└── global_config/
    ├── .claude/settings.json
    ├── .claude/projects/.../MEMORY.md
    └── .cursor/rules/...
```

---

## Feed to ChatGPT / Codex

1. Unzip and open **`txt_bundle.txt`**
2. Paste it as your **first message or system prompt**:

```
You are a coding assistant. Here is my full project context and AI assistant instructions:

[PASTE txt_bundle.txt HERE]

Now help me with: <your task>
```

### Via OpenAI API (Python)

```python
import openai

with open("txt_bundle.txt") as f:
    context = f.read()

response = openai.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": context},
        {"role": "user", "content": "Fix the authentication bug in app.py"}
    ]
)
print(response.choices[0].message.content)
```

### Via Codex CLI

```bash
codex --system-prompt "$(cat txt_bundle.txt)" "your task here"
```

---

## Requirements

- Python 3.10+
- No external packages required

### Python 3.9 compatibility

Change one line in the script:

```python
# From:
def safe_read(path: Path) -> str | None:

# To:
from typing import Optional
def safe_read(path: Path) -> Optional[str]:
```

---

## What Gets Skipped

The script automatically skips:

- `node_modules/`, `__pycache__/`, `.venv/`, `dist/`, `build/`
- `.git/`, `.idea/`, `.vscode/`
- Claude/Cursor internals: `debug/`, `file-history/`, `cache/`, `logs/`, `extensions/`
- Files larger than 512 KB

---

## License

MIT
