# Henry Orchestrator — Deployment Guide

## What's In This Package

```
henry-orchestrator/
├── HENRY.soul.md              # Main system prompt (THE CORE FILE)
├── config.yaml              # Configuration options
├── FIX-AND-DEPLOY.bat       # ONE-CLICK: Fix WSL2 + Deploy Henry (Windows)
├── fix-wsl2.ps1             # Fix blank WSL2 Ubuntu terminal
├── deploy-to-wsl2.sh        # Deploy Henry to OpenClaw (runs in WSL2)
├── install.sh               # Generic Linux installer
├── memory/
│   └── henry_memory.json    # Persistent memory template
└── protocols/
    ├── persistence-loop.md      # Never give up protocol
    ├── guardian-watchdog.md     # Always watching protocol
    ├── sub-agent-dispatch.md    # How to spawn agents
    ├── parallel-exploration.md  # MCTS-style parallel search
    └── agent-communication.md   # Agent-to-agent messaging
```

---

## WSL2 Deployment (Recommended)

If you're running OpenClaw on WSL2 Ubuntu (Windows), use the one-click method:

### One-Click Method

1. Download this entire `henry-orchestrator` folder to your Windows machine
2. Right-click **`FIX-AND-DEPLOY.bat`** → **Run as Administrator**
3. Done. It fixes your terminal AND deploys Henry.

### What the One-Click Does

| Step | Script | What Happens |
|------|--------|-------------|
| 1 | `fix-wsl2.ps1` | Shuts down WSL2, backs up your shell config, resets to Ubuntu defaults, restarts |
| 2 | (wait) | WSL2 initializes with working prompt |
| 3 | `deploy-to-wsl2.sh` | Finds OpenClaw, copies Henry files, tests gateway connection |
| 4 | (browser) | Opens `http://localhost:18789/agents` |

### Manual WSL2 Method

If you prefer to run each step yourself:

**Step 1: Fix blank terminal** (run in Windows PowerShell as Admin)
```powershell
powershell -ExecutionPolicy Bypass -File fix-wsl2.ps1
```

**Step 2: Deploy Henry** (run in WSL2 Ubuntu terminal after fix)
```bash
chmod +x deploy-to-wsl2.sh
./deploy-to-wsl2.sh
```

### WSL2 Troubleshooting

**Terminal still blank after fix?**
```powershell
# In PowerShell — full reset
wsl --shutdown
wsl --unregister Ubuntu
# Then reinstall Ubuntu from Microsoft Store
```

**Gateway not reachable from WSL2?**
```bash
# WSL2 should access Windows localhost automatically
# If not, try the Windows host IP:
cat /etc/resolv.conf | grep nameserver | awk '{print $2}'
# Use that IP instead of localhost
```

**OpenClaw not found?**
```bash
# Run deploy with explicit path
./deploy-to-wsl2.sh /path/to/your/openclaw
```

---

## Quick Deploy (5 Minutes)

### Step 1: Find Your OpenClaw Config Directory

Typical locations:
```bash
# Linux
~/.config/openclaw/
~/.openclaw/

# macOS
~/Library/Application Support/openclaw/
~/.openclaw/

# Windows
%APPDATA%\openclaw\
```

Find it with:
```bash
# If OpenClaw has a config command
openclaw config --path

# Or search for it
find ~ -type d -name "*openclaw*" 2>/dev/null
```

### Step 2: Copy the Soul File

The **HENRY.soul.md** file is the main system prompt. This is what transforms OpenClaw into Henry.

```bash
# Replace [OPENCLAW_DIR] with your actual path
cp HENRY.soul.md [OPENCLAW_DIR]/system.soul.md

# Or if OpenClaw uses a different naming convention:
cp HENRY.soul.md [OPENCLAW_DIR]/henry.soul.md
```

### Step 3: Update OpenClaw to Use the New Prompt

Depending on your OpenClaw version, do one of these:

**Option A: Config file reference**
```yaml
# In openclaw.yaml or config.yaml
system_prompt: "./henry.soul.md"
```

**Option B: Environment variable**
```bash
export OPENCLAW_SYSTEM_PROMPT="path/to/HENRY.soul.md"
```

**Option C: Command line**
```bash
openclaw --system-prompt ./HENRY.soul.md
```

### Step 4: Initialize Memory

```bash
# Create memory directory
mkdir -p [OPENCLAW_DIR]/memory/

# Copy memory template
cp memory/henry_memory.json [OPENCLAW_DIR]/memory/
```

### Step 5: Test It

```bash
openclaw

# Then say:
> Henry, what needs my attention today?
```

---

## Full Install (With All Features)

### 1. Copy Everything

```bash
# Copy entire deployment to OpenClaw directory
cp -r henry-orchestrator/* [OPENCLAW_DIR]/
```

### 2. Configure Memory Persistence

Edit `config.yaml`:
```yaml
memory:
  enabled: true
  persistence: true
  storage_path: "./memory/"
```

If OpenClaw supports custom config, point it to `config.yaml`:
```bash
openclaw --config ./config.yaml
```

### 3. Enable Guardian Mode (Optional)

The Guardian module watches for opportunities and threats. To enable automatic monitoring:

```yaml
# In config.yaml
guardian:
  enabled: true
  check_interval: "hourly"
```

### 4. Set Up Integrations (Optional)

Edit `config.yaml` to connect external services:

```yaml
integrations:
  calendar:
    enabled: true
    provider: "google"  # or "outlook"
    # Add credentials as needed

  email:
    enabled: true
    provider: "gmail"

  tasks:
    enabled: true
    provider: "todoist"
```

---

## If OpenClaw Uses a Different Format

### Converting Soul File to Plain Text

If your OpenClaw doesn't support `.soul.md` format:

```bash
# The soul file is just markdown - rename it
cp HENRY.soul.md henry_system_prompt.txt

# Or extract just the content (remove markdown headers if needed)
sed 's/^# //' HENRY.soul.md > henry_prompt.txt
```

### Converting to JSON Format

If OpenClaw expects JSON:

```json
{
  "name": "Henry",
  "system_prompt": "You are Henry, a personal AI orchestrator...",
  "memory_enabled": true,
  "modules": {
    "guardian": true,
    "reasoner": true,
    "dispatcher": true,
    "memory": true
  }
}
```

Use the content from `HENRY.soul.md` as the `system_prompt` value.

---

## Testing Your Installation

### Basic Test

```
You: Henry, introduce yourself.

Henry should respond: Describe itself as your digital twin, mention the four modules (Guardian, Reasoner, Dispatcher, Memory), and its prime directive.
```

### Persistence Test

```
You: Henry, remember that my favorite coffee is Ethiopian Yirgacheffe.

[Close and reopen OpenClaw]

You: Henry, what's my favorite coffee?

Henry should remember: Ethiopian Yirgacheffe (if memory persistence is working).
```

### Reasoning Test

```
You: Henry, should I invest $10,000 in Bitcoin right now?

Henry should respond: Run Monte Carlo scenarios (best/optimistic/base/pessimistic/worst), state confidence levels, recommend validation steps.
```

### Persistence Loop Test

```
You: Henry, find me the CEO email for a company that doesn't publish executive contact info.

Henry should: Try multiple approaches before giving up, never return empty-handed.
```

---

## Troubleshooting

### Henry isn't responding like the prompt says

1. Verify the soul file is being loaded:
   ```bash
   openclaw --verbose  # or --debug
   ```

2. Check if the system prompt is being read:
   - Some systems truncate long prompts
   - Try a shorter version first

### Memory isn't persisting

1. Check write permissions:
   ```bash
   ls -la [OPENCLAW_DIR]/memory/
   ```

2. Verify the memory file exists after a session:
   ```bash
   cat [OPENCLAW_DIR]/memory/henry_memory.json
   ```

### Guardian alerts aren't working

Guardian mode requires:
- Background process support in OpenClaw
- Or manual triggers ("Henry, check for alerts")

---

## Customization

### Adding Your Own Monitors

Edit `protocols/guardian-watchdog.md` to add custom monitoring categories.

### Changing Confidence Thresholds

In `config.yaml`:
```yaml
reasoner:
  confidence:
    min_threshold: 0.60  # Raise for more cautious behavior
```

### Adjusting Monte Carlo Probabilities

In `config.yaml`:
```yaml
monte_carlo:
  default_probabilities:
    best_case: 0.05      # Make best case rarer
    base_case: 0.50      # Weight toward base case
    worst_case: 0.05     # Make worst case rarer
```

---

## File Reference

| File | Purpose | Required |
|---|---|---|
| `HENRY.soul.md` | Core system prompt | YES |
| `config.yaml` | Configuration options | Optional |
| `memory/henry_memory.json` | Persistent memory template | For memory features |
| `protocols/*.md` | Detailed protocols | Reference only |

The only required file is **HENRY.soul.md**. Everything else enhances functionality.

---

## Quick Commands After Install

| Command | What It Does |
|---|---|
| "Morning brief" | Daily overview |
| "What needs attention?" | Priority alerts |
| "Research [topic]" | Spawn research agent |
| "Analyze [data]" | Get insights |
| "Monte Carlo on [decision]" | Scenario analysis |
| "Remember that [fact]" | Store in memory |
| "What do you know about [topic]?" | Query memory |

---

## Need Help?

The protocols directory contains detailed documentation:
- `persistence-loop.md` — How Henry never gives up
- `guardian-watchdog.md` — How monitoring works
- `sub-agent-dispatch.md` — How to spawn agents
- `parallel-exploration.md` — MCTS-style parallel search
- `agent-communication.md` — Agent-to-agent messaging

Each protocol includes examples and can be customized.
