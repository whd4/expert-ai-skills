# Henry Orchestrator — Deployment Guide

## What's In This Package

```
henry-orchestrator/
├── HENRY.solmd              # Main system prompt (THE CORE FILE)
├── config.yaml              # Configuration options
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

### Step 2: Copy the SOLMD File

The **HENRY.solmd** file is the main system prompt. This is what transforms OpenClaw into Henry.

```bash
# Replace [OPENCLAW_DIR] with your actual path
cp HENRY.solmd [OPENCLAW_DIR]/system.solmd

# Or if OpenClaw uses a different naming convention:
cp HENRY.solmd [OPENCLAW_DIR]/henry.solmd
```

### Step 3: Update OpenClaw to Use the New Prompt

Depending on your OpenClaw version, do one of these:

**Option A: Config file reference**
```yaml
# In openclaw.yaml or config.yaml
system_prompt: "./henry.solmd"
```

**Option B: Environment variable**
```bash
export OPENCLAW_SYSTEM_PROMPT="path/to/HENRY.solmd"
```

**Option C: Command line**
```bash
openclaw --system-prompt ./HENRY.solmd
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

### Converting SOLMD to Plain Text

If your OpenClaw doesn't support `.solmd` format:

```bash
# The SOLMD is just markdown - rename it
cp HENRY.solmd henry_system_prompt.txt

# Or extract just the content (remove markdown headers if needed)
sed 's/^# //' HENRY.solmd > henry_prompt.txt
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

Use the content from `HENRY.solmd` as the `system_prompt` value.

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

1. Verify the SOLMD file is being loaded:
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
| `HENRY.solmd` | Core system prompt | YES |
| `config.yaml` | Configuration options | Optional |
| `memory/henry_memory.json` | Persistent memory template | For memory features |
| `protocols/*.md` | Detailed protocols | Reference only |

The only required file is **HENRY.solmd**. Everything else enhances functionality.

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
