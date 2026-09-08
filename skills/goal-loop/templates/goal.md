# Goal: <short title>

**Serves intent:** intent/<date>-<slug>.md
**Selected because:** impact <high/med/low>, confidence <0.0–1.0>, cost <iterations or hours>

## Completion condition (machine-checkable)

```
<command>            must exit 0
<command> | <filter> must print <exact value>
```

If no such command exists yet, the first sub-goal below is to build one.

## Sub-goals

Keep as JSON when the list is long; models corrupt Markdown checklists more often.

- [ ] 0. Build or confirm the check
- [ ] 1.
- [ ] 2.
- [ ] 3.

## Budgets

| Horizon | Max iterations | Stall rule |
|---|---|---|
| Micro (edit → check) | 30 | 3 identical outputs → change approach |
| Macro (feature) | 10 | no metric movement in 20 micro loops → write diagnosis, escalate |
| Session | until done | commit + progress.md before context ends |

## Escalation set for this goal

Only these stop the loop:

- 
