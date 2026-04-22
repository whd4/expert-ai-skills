# Session Handoff — Mission Control Build

**Date:** 2026-04-22
**Branch:** `claude/monte-carlo-claw-predictions-njtce`
**Status:** Ready to continue locally

---

## What Was Built This Session

### 1. `mission-control.html` (red/white/grey/black palette)
Single-file HTML dashboard, 10 panels, read-aloud buttons, side-nav dots, keyboard nav.

**Locked palette (9 CSS vars):**
```
--bg-black:       #0A0A0A
--bg-panel:       #141414
--bg-elevated:    #1C1C1C
--border:         #2A2A2A
--text-white:     #F5F5F5
--text-grey:      #9A9A9A
--text-muted:     #5A5A5A
--accent-red:     #DC2626
--accent-red-dim: #7F1D1D
```

**Panels:**
1. STATUS — honest read + 4 gauges (capability/signal/revenue/network)
2. ASYMMETRIC ADVANTAGE — cold founder vs warm F500 path
3. ONE-SHOT PROTOCOL — don't burn the contact
4. THE MEETING — 30-min flight plan (open/demo/propose/close)
5. THE NARROW BUILD — pilot scope rules
6. THE 90-DAY PILOT — phase structure + success metric
7. COMPOUND PATH — revenue trajectory SVG chart + flywheel
8. TRAPS — 5 common solo-founder fatals
9. DIVISION OF LABOR — me does / you do columns + handoff spec
10. ACTION — inputs form: pick vertical, name contact, book meeting

### 2. `mission-control-bluegold.html` (navy/gold variant)
Same 10 panels, swapped palette:
```
--bg-black:       #0A0E1A  (deep navy-black)
--bg-panel:       #111827
--bg-elevated:    #1E293B
--border:         #334155
--text-white:     #F1F5F9
--text-grey:      #94A3B8
--text-muted:     #64748B
--accent (red): #D4A64A  (gold) [variable name kept, hex swapped]
--accent-dim:   #8B6B2E
```

### 3. HENRY VIZ launch button
In top-bar of both HTML files.
- **Click** → opens `localStorage.henry_url` (defaults to `http://localhost:3000`)
- **Shift+click** → prompts to set a new URL, persists to localStorage

### 4. Obsidian CSS snippets
- `obsidian/mission-control-red.css`
- `obsidian/mission-control-bluegold.css`
- `obsidian/README.md` (PowerShell install instructions)

Drop into `<vault>/.obsidian/snippets/`, enable one in Settings → Appearance.

### 5. Codex P1/P2 bug fixes pushed
- `skills/monte-carlo-predictor/engine/distributions.py`: zero-rate Poisson no longer returns -1
- `skills/monte-carlo-predictor/engine/expressions.py`: `and`/`or` use Python semantics; `min`/`max` broadcast scalars correctly
- `skills/prediction-toolkit/engine/exponential_smoothing.py`: `seasonal_periods` validated against data length
- `skills/prediction-toolkit/engine/router.py`: keyword matching uses word boundaries (regex `\b`)

---

## Key Decisions Made

### OpenClaw / OAuth policy
- **April 4, 2026**: Anthropic banned OAuth-token extraction for third-party tools (OpenClaw, OpenCode, etc.) on consumer subscriptions.
- **Still sanctioned**: `claude -p` subprocess reuse. OpenClaw treats this as allowed. Anthropic staff (Boris, Claude Code team) publicly confirmed on Twitter.
- **Decision path: Path 1** — OpenClaw should call `claude.exe` as a subprocess, not extract OAuth tokens or run a proxy.
- Path 2 (claude-max-api-proxy) still works but adds a community-maintained daemon.

### Palette
- Both dashboards exist. User can pick either.
- Red version is "mission control severe". Gold version is "classic/warm".

---

## What's NOT Done Yet (Next Session Priorities)

### 1. Verify mission-control renders in browser
```powershell
Start-Process "C:\Users\whitt\Development\expert-ai-skills\mission-control.html"
Start-Process "C:\Users\whitt\Development\expert-ai-skills\mission-control-bluegold.html"
```

### 2. Wire OpenClaw to CLI subprocess (Path 1)
```powershell
claude /status
Remove-Item Env:ANTHROPIC_API_KEY -ErrorAction SilentlyContinue
openclaw onboard   # pick "Claude CLI reuse"
openclaw models status
```

### 3. Install Obsidian themes
```powershell
$vault = "$env:USERPROFILE\Documents\<VaultName>\.obsidian\snippets"
New-Item -ItemType Directory -Force -Path $vault
Copy-Item "C:\Users\whitt\Development\expert-ai-skills\obsidian\*.css" $vault
```

### 4. Link skills globally for Claude Code (admin PowerShell)
```powershell
New-Item -ItemType SymbolicLink -Path "$env:USERPROFILE\.claude\skills\prediction-toolkit" -Target "C:\Users\whitt\Development\expert-ai-skills\skills\prediction-toolkit"
New-Item -ItemType SymbolicLink -Path "$env:USERPROFILE\.claude\skills\monte-carlo-predictor" -Target "C:\Users\whitt\Development\expert-ai-skills\skills\monte-carlo-predictor"
```

### 5. Hermes upgrade
- Not in this repo. User has Hermes locally. Needs either: (a) push Hermes to this repo, or (b) do upgrades in a local Claude session pointed at Hermes directory.

### 6. OpenClaw upgrade
- User said OpenClaw had major updates today. After Path 1 is wired, run `openclaw upgrade` or equivalent.

### 7. Database integration
- User wants mission-control to show live numbers from a local database.
- Unknowns: which DB (Postgres? Neo4j? SQLite?), where it lives, what tables.
- Gating question before writing any integration code.

### 8. The real Panel 10 ask
Human-only inputs the user hasn't filled yet:
- Which vertical (one industry)?
- Which contact (one person at one F500)?
- Meeting booked by when (72-hour deadline)?

No engineering progress compounds until these three are answered.

---

## Repo State
```
/home/user/expert-ai-skills
├── mission-control.html            [NEW this session — 10 panels red]
├── mission-control-bluegold.html   [NEW this session — 10 panels gold]
├── SESSION_HANDOFF.md              [this file]
├── NEXT_SESSION_PROMPT.md          [paste into new session]
├── obsidian/
│   ├── mission-control-red.css
│   ├── mission-control-bluegold.css
│   └── README.md
├── skills/
│   ├── monte-carlo-predictor/      [bug fixes pushed]
│   └── prediction-toolkit/         [bug fixes pushed]
└── CLAUDE.md                       [project guidance]
```

Latest commits on branch `claude/monte-carlo-claw-predictions-njtce`:
- `54de4ec` feat: add navy/gold variant + Henry launch button + Obsidian themes
- `d555971` fix: address Codex P1/P2 review findings
- `24badd9` feat: add Panel 10 (ACTION) to complete mission-control dashboard
- `0619759` style: lock to white/grey/red/black design system

---

## User Context (for the new session)

- Solo founder building an AI agent orchestration business
- Has Fortune 500 warm contacts (the asymmetric advantage)
- Zero revenue, zero customers — needs to convert one warm contact into one signed pilot
- Has been building in isolation too long; biggest risk is not shipping to a real customer
- Wants a practical co-pilot, not "frontier labs" flattery
- Uses Windows + PowerShell
- Has Obsidian vault + HENRY visualizer + Hermes + OpenClaw stack
- Max subscription (not API-key based)

## Communication style preferences
- Direct, short, practical
- No emoji unless requested
- Honest read over flattery
- "Execute first, ask questions second"
- Sharp corners, no pill shapes (reflected in HTML design)
