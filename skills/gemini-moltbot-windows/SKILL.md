---
name: gemini-moltbot-windows
description: "Special instructions for using Google Gemini 3 to build a Molt.bot desktop application on Windows PC. Covers setup, architecture, bot logic, packaging, and deployment."
version: "1.0.0"
tags: ["gemini", "ai-bot", "windows", "molt-bot", "desktop-app", "automation"]
---

# Building a Molt.bot for Windows PC with Gemini 3

## Overview

Step-by-step instructions for leveraging Google Gemini 3 to design, build, and deploy a **Molt.bot** — an AI-powered desktop bot for Windows that automates tasks, sheds outdated workflows, and continuously self-improves. "Molt" refers to the bot's ability to shed old behaviors and adopt new ones, making it an adaptive personal automation agent.

## When to Use

- You want to build an AI-powered desktop bot on Windows using Gemini 3 as the reasoning engine
- You need a self-improving automation agent that adapts to changing workflows
- You want a local-first Windows application with cloud AI capabilities
- You need a bot that can interact with Windows apps, files, and system APIs

---

## Prerequisites

### System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| OS | Windows 10 21H2+ | Windows 11 23H2+ |
| Python | 3.10+ | 3.12+ |
| RAM | 8 GB | 16 GB |
| Disk | 2 GB free | 10 GB free |
| Network | Broadband | Broadband |

### Accounts & API Keys

1. **Google AI Studio** account — obtain a Gemini 3 API key at `https://aistudio.google.com/apikey`
2. Store the key in a Windows environment variable:
   ```powershell
   [System.Environment]::SetEnvironmentVariable("GEMINI_API_KEY", "your-key-here", "User")
   ```

### Toolchain Setup

```powershell
# Install Python (if not present) via winget
winget install Python.Python.3.12

# Create project directory
mkdir C:\Projects\molt-bot
cd C:\Projects\molt-bot

# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install core dependencies
pip install google-genai pyside6 watchdog pystray pyautogui schedule keyring
```

---

## Architecture

```
molt-bot/
├── main.py                 # Entry point, system tray launcher
├── config.yaml             # User preferences and task definitions
├── core/
│   ├── __init__.py
│   ├── gemini_client.py    # Gemini 3 API wrapper
│   ├── molt_engine.py      # Adaptive task engine (molt logic)
│   ├── task_runner.py      # Task execution and scheduling
│   └── memory.py           # Conversation and task history store
├── plugins/
│   ├── __init__.py
│   ├── file_organizer.py   # File sorting and cleanup plugin
│   ├── app_launcher.py     # Application automation plugin
│   └── clipboard_agent.py  # Clipboard monitoring plugin
├── ui/
│   ├── __init__.py
│   ├── tray.py             # System tray icon and menu
│   └── dashboard.py        # Optional PySide6 dashboard window
├── tests/
│   └── test_molt_engine.py
└── requirements.txt
```

### Component Roles

| Component | Purpose |
|-----------|---------|
| `gemini_client.py` | Sends prompts to Gemini 3, handles streaming responses, manages token budgets |
| `molt_engine.py` | Core "molting" logic — evaluates task success, prunes underperforming strategies, generates improved approaches via Gemini |
| `task_runner.py` | Executes scheduled and event-driven tasks using plugins |
| `memory.py` | SQLite-backed store for conversation context, task outcomes, and learned preferences |
| `tray.py` | Lightweight system tray presence so the bot runs unobtrusively |

---

## Step-by-Step Build Instructions

### Step 1: Gemini 3 Client

Create the API wrapper that all components use to communicate with Gemini 3.

```python
# core/gemini_client.py
import os
from google import genai

class GeminiClient:
    def __init__(self):
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise EnvironmentError("GEMINI_API_KEY not set")
        self.client = genai.Client(api_key=api_key)
        self.model = "gemini-3"

    def ask(self, prompt: str, system_instruction: str = "") -> str:
        """Send a prompt to Gemini 3 and return the text response."""
        config = {}
        if system_instruction:
            config["system_instruction"] = system_instruction
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=config,
        )
        return response.text

    def ask_structured(self, prompt: str, schema: dict) -> dict:
        """Request JSON-structured output from Gemini 3."""
        import json
        config = {
            "response_mime_type": "application/json",
            "response_schema": schema,
        }
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=config,
        )
        return json.loads(response.text)
```

### Step 2: Molt Engine (Self-Improvement Core)

The molt engine is what makes this bot unique — it periodically reviews its own task performance and asks Gemini 3 to suggest better strategies.

```python
# core/molt_engine.py
import json
import datetime
from core.gemini_client import GeminiClient
from core.memory import MemoryStore

MOLT_SYSTEM_PROMPT = """You are the Molt Engine. You review task execution logs
and suggest improved strategies. For each task, output JSON with:
- task_id: the task identifier
- assessment: "keep", "modify", or "discard"
- reasoning: why this assessment
- improved_strategy: new approach if assessment is "modify"
"""

class MoltEngine:
    def __init__(self, gemini: GeminiClient, memory: MemoryStore):
        self.gemini = gemini
        self.memory = memory

    def evaluate_and_molt(self):
        """Review recent task outcomes and evolve strategies."""
        logs = self.memory.get_recent_task_logs(days=7)
        if not logs:
            return []

        prompt = (
            "Review these task execution logs and suggest improvements:\n"
            + json.dumps(logs, indent=2)
        )
        result = self.gemini.ask(prompt, system_instruction=MOLT_SYSTEM_PROMPT)
        recommendations = json.loads(result)

        for rec in recommendations:
            if rec["assessment"] == "discard":
                self.memory.disable_task(rec["task_id"])
            elif rec["assessment"] == "modify":
                self.memory.update_strategy(rec["task_id"], rec["improved_strategy"])

        self.memory.log_molt_event(datetime.datetime.now(), recommendations)
        return recommendations
```

### Step 3: Task Runner

```python
# core/task_runner.py
import importlib
import schedule
import time
import threading
from core.memory import MemoryStore

class TaskRunner:
    def __init__(self, memory: MemoryStore):
        self.memory = memory
        self.plugins = {}

    def load_plugin(self, name: str):
        """Dynamically load a plugin from the plugins/ directory."""
        module = importlib.import_module(f"plugins.{name}")
        self.plugins[name] = module
        return module

    def run_task(self, task_id: str, plugin_name: str, action: str, **kwargs):
        """Execute a task via a plugin and log the outcome."""
        plugin = self.plugins.get(plugin_name)
        if not plugin:
            plugin = self.load_plugin(plugin_name)

        func = getattr(plugin, action)
        try:
            result = func(**kwargs)
            self.memory.log_task(task_id, plugin_name, action, "success", str(result))
            return result
        except Exception as e:
            self.memory.log_task(task_id, plugin_name, action, "failure", str(e))
            raise

    def start_scheduler(self):
        """Run scheduled tasks in a background thread."""
        def loop():
            while True:
                schedule.run_pending()
                time.sleep(1)
        t = threading.Thread(target=loop, daemon=True)
        t.start()
```

### Step 4: Memory Store

```python
# core/memory.py
import sqlite3
import json
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.expanduser("~"), ".molt-bot", "memory.db")

class MemoryStore:
    def __init__(self):
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self._init_tables()

    def _init_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS task_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT, plugin TEXT, action TEXT,
                status TEXT, detail TEXT,
                ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS strategies (
                task_id TEXT PRIMARY KEY,
                strategy TEXT, enabled INTEGER DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS molt_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TIMESTAMP, recommendations TEXT
            );
        """)

    def log_task(self, task_id, plugin, action, status, detail):
        self.conn.execute(
            "INSERT INTO task_logs (task_id, plugin, action, status, detail) VALUES (?,?,?,?,?)",
            (task_id, plugin, action, status, detail),
        )
        self.conn.commit()

    def get_recent_task_logs(self, days=7):
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        cur = self.conn.execute(
            "SELECT task_id, plugin, action, status, detail, ts FROM task_logs WHERE ts > ?",
            (cutoff,),
        )
        return [dict(zip(["task_id","plugin","action","status","detail","ts"], r)) for r in cur.fetchall()]

    def disable_task(self, task_id):
        self.conn.execute("UPDATE strategies SET enabled=0 WHERE task_id=?", (task_id,))
        self.conn.commit()

    def update_strategy(self, task_id, strategy):
        self.conn.execute(
            "INSERT OR REPLACE INTO strategies (task_id, strategy, enabled) VALUES (?,?,1)",
            (task_id, json.dumps(strategy)),
        )
        self.conn.commit()

    def log_molt_event(self, ts, recommendations):
        self.conn.execute(
            "INSERT INTO molt_events (ts, recommendations) VALUES (?,?)",
            (ts.isoformat(), json.dumps(recommendations)),
        )
        self.conn.commit()
```

### Step 5: System Tray & Entry Point

```python
# ui/tray.py
import pystray
from PIL import Image, ImageDraw

def create_icon():
    img = Image.new("RGB", (64, 64), color=(30, 30, 30))
    d = ImageDraw.Draw(img)
    d.ellipse([12, 12, 52, 52], fill=(0, 200, 120))
    d.text((22, 22), "M", fill="white")
    return img

def build_tray(on_quit, on_dashboard, on_molt_now):
    icon = pystray.Icon(
        "molt-bot",
        create_icon(),
        "Molt.bot",
        menu=pystray.Menu(
            pystray.MenuItem("Dashboard", on_dashboard),
            pystray.MenuItem("Molt Now", on_molt_now),
            pystray.MenuItem("Quit", on_quit),
        ),
    )
    return icon
```

```python
# main.py
import sys
import threading
from core.gemini_client import GeminiClient
from core.memory import MemoryStore
from core.molt_engine import MoltEngine
from core.task_runner import TaskRunner
from ui.tray import build_tray
import schedule

def main():
    gemini = GeminiClient()
    memory = MemoryStore()
    molt = MoltEngine(gemini, memory)
    runner = TaskRunner(memory)

    # Schedule a molt cycle every 24 hours
    schedule.every(24).hours.do(molt.evaluate_and_molt)
    runner.start_scheduler()

    # System tray
    def on_quit(icon, item):
        icon.stop()
        sys.exit(0)

    def on_dashboard(icon, item):
        print("Dashboard placeholder — integrate PySide6 window here")

    def on_molt_now(icon, item):
        threading.Thread(target=molt.evaluate_and_molt, daemon=True).start()

    icon = build_tray(on_quit, on_dashboard, on_molt_now)
    icon.run()

if __name__ == "__main__":
    main()
```

---

## Example Plugin: File Organizer

```python
# plugins/file_organizer.py
import os
import shutil
from pathlib import Path

CATEGORY_MAP = {
    "Documents": [".pdf", ".docx", ".txt", ".xlsx", ".pptx", ".csv"],
    "Images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp"],
    "Videos": [".mp4", ".mkv", ".avi", ".mov", ".wmv"],
    "Audio": [".mp3", ".wav", ".flac", ".aac", ".ogg"],
    "Archives": [".zip", ".rar", ".7z", ".tar", ".gz"],
    "Code": [".py", ".js", ".ts", ".html", ".css", ".java", ".cpp"],
}

def organize(directory: str) -> dict:
    """Sort files in a directory into categorized subfolders."""
    directory = Path(directory)
    moved = {}
    for file in directory.iterdir():
        if not file.is_file():
            continue
        ext = file.suffix.lower()
        category = "Other"
        for cat, exts in CATEGORY_MAP.items():
            if ext in exts:
                category = cat
                break
        dest_dir = directory / category
        dest_dir.mkdir(exist_ok=True)
        shutil.move(str(file), str(dest_dir / file.name))
        moved.setdefault(category, []).append(file.name)
    return moved
```

---

## Prompting Gemini 3 Effectively for Molt.bot

When asking Gemini 3 to generate new strategies or analyze tasks, use these prompt patterns:

### Strategy Generation Prompt
```
You are Molt.bot's planning engine. Given the user's goal and past task logs,
produce a JSON execution plan with steps, required plugins, and fallback actions.

Goal: {user_goal}
Past logs: {recent_logs}

Output format:
{
  "steps": [{"action": "...", "plugin": "...", "params": {...}}],
  "fallback": "description of what to do if a step fails"
}
```

### Self-Assessment Prompt
```
Review these 7-day task logs. For each unique task, rate effectiveness (1-10)
and suggest whether to keep, modify, or discard the current approach.
Provide concrete improved strategies for any task rated below 7.
```

---

## Packaging for Windows Distribution

### Option A: PyInstaller (Single .exe)

```powershell
pip install pyinstaller
pyinstaller --onefile --windowed --name MoltBot --icon=icon.ico main.py
# Output: dist/MoltBot.exe
```

### Option B: MSIX Installer (Windows Store ready)

1. Install the **MSIX Packaging Tool** from the Microsoft Store
2. Run PyInstaller first to get the `.exe`
3. Use the MSIX tool to wrap the `.exe` into a signed package
4. Distribute via sideloading or the Microsoft Store

### Auto-Start on Login

```powershell
# Add to Windows startup via registry
$path = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
Set-ItemProperty -Path $path -Name "MoltBot" -Value "C:\Path\To\MoltBot.exe"
```

---

## Security Best Practices

- **Never hard-code API keys.** Use `keyring` or Windows Credential Manager.
- **Limit plugin permissions.** Plugins should not execute arbitrary shell commands without user approval.
- **Validate Gemini output.** Always parse and validate JSON responses before executing any actions.
- **Sandbox file operations.** Restrict file operations to user-approved directories only.
- **Log everything.** The memory store should record all actions for auditability.

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `GEMINI_API_KEY not set` | Restart terminal after setting the env var, or set it in System Properties |
| `ModuleNotFoundError` | Ensure the virtual environment is activated: `.\.venv\Scripts\Activate.ps1` |
| System tray icon not appearing | Install `Pillow`: `pip install Pillow` |
| Rate limit errors from Gemini | Add retry logic with exponential backoff in `gemini_client.py` |
| Bot not starting on login | Verify the registry path points to the correct `.exe` location |

---

## Related Skills

- @[skills/prompt-engineering] — Craft better prompts for Gemini 3
- @[skills/ai-agent-development] — General AI agent design patterns
- @[skills/windows-automation] — Windows-specific automation techniques
- @[skills/api-integration] — API client best practices
