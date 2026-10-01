# Goal: <short title>

**Serves intent:** intent/<date>-<slug>.md
**Selected because:** impact <high/med/low>, confidence <0.0–1.0>, cost <iterations or hours>

## Completion condition (machine-checkable)

```
<command>                                          must exit 0
test "$(<command> | <filter>)" = "<exact value>"   must exit 0
```

Every condition is pass or fail by **exit code only**; that is all `scripts/goal-check.sh` and `/goal` read. To require an exact printed value, put the comparison inside the command as above, so a mismatch exits nonzero. Never write "must print X" on its own.

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
| Micro (edit → check) | 30 | 3 consecutive identical failed checks → change approach |
| Macro (feature) | 10 | no metric movement in 20 micro loops → write diagnosis, escalate |
| Session | until done | commit + progress.md before context ends |

## Escalation set for this goal

Only these stop the loop:

-
