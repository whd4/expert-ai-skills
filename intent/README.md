# intent/

Version-controlled home for intent files, following Anthropic's AI-native SDLC playbook.

One file per request: `YYYY-MM-DD-<slug>.md`, written from the originator's own words using `skills/goal-loop/templates/intent.md`. The originator may edit it before or after it is committed. Each file states what is wanted, why, under which constraints, which readings were considered, and which decisions were made without asking.

The intent file is the first link in the artifact chain:

```
intent.md → goal.md → plan → diff → check log → progress.md
```

See `skills/goal-loop/SKILL.md` for how a session turns an intent into a finished, verified change.
