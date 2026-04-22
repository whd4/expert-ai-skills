# Paste This Into Your New Local Claude Session

Copy everything below the line into the first message of your new local Claude Code session. It catches the new session up to speed.

---

I'm continuing work from a previous Claude session. Full context in `SESSION_HANDOFF.md` at repo root — please read that first.

**Branch:** `claude/monte-carlo-claw-predictions-njtce` (already pulled locally)
**Repo:** `C:\Users\whitt\Development\expert-ai-skills`

**Summary of prior session:**
- Built `mission-control.html` (10-panel dashboard, red/white/grey/black palette)
- Built `mission-control-bluegold.html` (same 10 panels, navy/gold variant)
- Added HENRY VIZ launch button to top-bar of both (Shift+click to set URL)
- Created `obsidian/` CSS snippets + README for Obsidian theming
- Fixed Codex P1/P2 bugs in `skills/monte-carlo-predictor` and `skills/prediction-toolkit`
- Confirmed Path 1 for OpenClaw: `claude -p` subprocess reuse (sanctioned by Anthropic post-April-4 ban)

**Immediate tasks I want you to do, in order:**

1. `Start-Process "mission-control.html"` — verify dashboard renders, confirm design looks right
2. `Start-Process "mission-control-bluegold.html"` — verify navy/gold variant
3. Run `claude /status` and `openclaw --version` — tell me what's installed
4. Wire OpenClaw to Path 1 (CLI subprocess reuse):
   ```powershell
   Remove-Item Env:ANTHROPIC_API_KEY -ErrorAction SilentlyContinue
   openclaw onboard   # pick "Claude CLI reuse"
   openclaw models status
   ```
5. Install Obsidian themes — first tell me my vault path (`$env:USERPROFILE\Documents\<VaultName>\.obsidian\snippets`)
6. Symlink skills globally (needs admin PowerShell):
   ```powershell
   New-Item -ItemType SymbolicLink -Path "$env:USERPROFILE\.claude\skills\prediction-toolkit" -Target "$PWD\skills\prediction-toolkit"
   New-Item -ItemType SymbolicLink -Path "$env:USERPROFILE\.claude\skills\monte-carlo-predictor" -Target "$PWD\skills\monte-carlo-predictor"
   ```

**After that, bigger asks:**
- Upgrade Hermes to the latest OpenClaw (Hermes is at `<ask me for path>`)
- Run `openclaw upgrade` for the latest OpenClaw updates
- Wire mission-control to my local database (I'll tell you which DB + location)
- Help me write a pre-meeting brief for the first F500 contact I'm meeting

**Preferences (important):**
- Direct, short, practical — no flattery, no "frontier labs" language
- Execute first, ask questions second
- Sharp design (no pills, 0-2px corners, locked palettes)
- Honest reads, including when I'm wrong about something
- Windows PowerShell user

Start by reading `SESSION_HANDOFF.md`, then do step 1 above.
