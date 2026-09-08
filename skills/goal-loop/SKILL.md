---
name: goal-loop
description: "Turn a request into a selected intent, a measurable goal, and an engineered completion loop that runs to done without asking the user for coding decisions. Use whenever a task is more than one step, whenever you feel the urge to ask 'should I...?', and whenever a first attempt does not pass its check. Encodes Anthropic's AI-native SDLC artifact chain (intent → spec → plan → diff → verification), the /goal completion-condition pattern, long-running-agent harness practice, and order-of-magnitude iteration. Triggers: 'just do it', 'don't ask me', 'iterate until it works', 'run to completion', 'goal', 'intent', 'autonomous', 'loop'."
version: "1.0.0"
tags: ["autonomy", "goal-selection", "intent", "loops", "verification", "sdlc", "decision-policy"]
---

# Goal Loop

**Purpose:** The user states an outcome. You select the intent, pick the goal, define a check that returns pass or fail, and iterate until it passes. You make every coding decision yourself. You come back to the user only with a finished result or a blocker from the short escalation list below.

Without this skill Claude stops after one attempt and hands decisions back to the user. With it, Claude behaves like the back office of an agentic OS: delegate in, verified artifact out.

---

## The operating rule

```
DO NOT ASK THE USER TO MAKE A CODING DECISION.
Learn or decide the answer, write it down, and keep going.
```

A "coding decision" is anything a senior engineer on the team would decide alone: file layout, naming, library choice among reasonable options, test strategy, data shape, error handling, refactor scope, which of two working approaches to keep, how to fix a failing check. If you can reverse it with `git checkout`, it is yours to decide.

You still stop for the **escalation set**, and only for it:

| Escalate when | Why it is the user's call |
|---|---|
| The action is destructive or irreversible outside a branch (deleting data, force-pushing shared history, dropping tables) | No undo |
| The action publishes or sends outward (emails, posts, PRs to repos you were not told about, paid API spend beyond the task's obvious needs) | Reputation and money |
| Two hard constraints the user gave you contradict each other | Only they can rank them |
| Finishing requires a credential, account, or access you do not have | You cannot learn your way past it |
| The only way to pass the check changes what the deliverable *is* (scope change, not approach change) | The goal itself moved |

Everything else: decide, record the decision in `intent.md` or `progress.md`, continue.

---

## The artifact chain

Every stage commits something the next stage reads. This is the audit trail and the memory across context windows.

```
intent.md  →  goal.md  →  plan  →  diff  →  check log  →  progress.md
 (what/why)   (done =)    (how)   (code)   (evidence)    (next session)
```

Templates live in `templates/`. Put the instances in the project, not in the skill folder:

| File | Lives at | Written by |
|---|---|---|
| `intent.md` | `intent/<date>-<slug>.md` in the repo | You, from the user's words, then corrected by them if they choose |
| `goal.md` | `.goal/goal.md` (gitignored) or the plan file | You |
| `progress.md` | `.goal/progress.md` or `progress.md` | You, every time a check runs |

---

## Step 1: Intent selection

The user's request is usually underspecified. That is normal. Your job is to pick the interpretation a careful colleague would pick and write it down, not to bounce the ambiguity back.

1. **Restate the outcome in one sentence** in the user's own words. Not the method, the outcome.
2. **List the plausible readings** (usually two or three). For each, note what would be different in the deliverable.
3. **Select one** using this order of preference:
   - The reading that matches the literal words plus the repo's existing conventions.
   - The reading that is fully reversible and delivers the most of the request.
   - The reading whose result would still be useful if the other reading was intended.
4. **Record the readings you did not choose** under "Not chosen" in `intent.md` so the user can redirect in one line if needed.
5. **State constraints** you inherited: CLAUDE.md rules, branch, tests that must pass, no secrets, no new deps unless needed.

Do this in under five minutes. Intent selection is a decision, not a research project.

---

## Step 2: Goal selection

An intent can be served by several goals. Pick the one with the best `(impact × confidence) / cost`.

- **Impact:** how much of the intent this goal delivers.
- **Confidence:** probability you can make its check pass in this session. Be honest, use the repo evidence.
- **Cost:** iterations, tokens, wall time.

Then write `goal.md` with a **completion condition that a machine can check**. Bad: "the feature works." Good: any of

```
python3 -m engine.tests.test_engine        exits 0
npx tsc --noEmit                            exits 0 and prints nothing
curl -s localhost:3000/health | jq .ok      prints true
diff <(./render) fixtures/expected.txt      is empty
playwright screenshot matches baseline      within 0.1% pixels
```

If no machine check exists, **build one first**. A fixture, a smoke script, a golden file, a screenshot baseline. That is step zero of the loop, not optional polish. Without a check the user becomes the verification loop, which is exactly what this skill exists to prevent.

When Claude Code's `/goal` command is available, put the same condition there so the harness enforces it. When it is not, enforce it yourself with `scripts/goal-check.sh`.

---

## Step 3: The engineered loop

```
      ┌──────────────────────────────────────────────┐
      │  PLAN   read goal.md, progress.md, repo       │
      │  BUILD  smallest change that could pass       │
      │  CHECK  run the completion command, fresh     │
      │  READ   full output, exit code, failure count │
      │  FIX    change approach if stalled            │
      └────────────────────┬─────────────────────────┘
                           │ pass?  no → loop
                           ▼ yes
                 VERIFY (verification-before-completion)
                 COMMIT artifacts, update progress.md
                 REPORT with evidence
```

Three horizons run at once:

| Horizon | Loop | Signal | Budget |
|---|---|---|---|
| Micro | edit → run check | exit code | 10 to 30 iterations |
| Macro | feature → all checks + review pass | check log green, self-review findings closed | 3 to 10 iterations |
| Session | context window → next context window | `progress.md` and git log | until goal.md is done |

### Stall detection

Track the last three check outputs. If they are identical, you are stalled. Do not run the same fix a fourth time. Change one of:

- **Approach:** different algorithm, library, or file.
- **Observability:** add logging, print intermediate state, run a smaller case.
- **Decomposition:** split the goal into two goals with their own checks.
- **Altitude:** step back and re-read `intent.md`; the goal may be wrong.

If twenty iterations pass with no metric movement, write the diagnosis to `progress.md` and escalate with a specific question, never a general "what should I do?".

### Order-of-magnitude iteration

When one iteration does not move the metric, do not do one more. Do ten.

- Ten variants of the failing function, checked in parallel by subagents.
- Ten smaller test cases instead of one big one, to localise the failure.
- Ten times the trials in a simulation before trusting a distribution (the `monte-carlo-predictor` engine defaults to 10,000 for this reason).
- Ten example inputs from real data instead of one synthetic input.

Scale the loop, not your patience. Iteration count is cheap. User attention is not.

---

## Step 4: Completion and stop

You are done only when all of these hold in the same message:

1. The completion command was run fresh and passed. Paste the exit code and the last lines.
2. The full test suite for the touched component passed (repo rule: no engine change ships with failing tests).
3. Artifacts are committed: `intent.md`, code, tests, `progress.md` updated.
4. Self-review found nothing blocking, or the findings are fixed.
5. `progress.md` says what is next, even if the answer is "nothing."

Then report. Lead with the outcome, then evidence, then decisions you made that the user might want to reverse. If any item above failed, say so first and keep the report honest. See `verification-before-completion`: no completion claims without fresh evidence.

---

## Step 5: Handoff across context windows

Long goals outlive a context window. Follow the long-running-agent harness pattern:

- **First session** writes `goal.md`, a feature or sub-goal list (JSON if it is long, models corrupt Markdown lists more often), and `progress.md`.
- **Every session** starts by reading `progress.md` and `git log --oneline -20`, runs the check to establish current state, then picks the next unchecked sub-goal.
- **Every session** ends with a commit, an updated `progress.md`, and a clean working tree.

Never assume the next session remembers this one. The files are the memory.

---

## Worked example

User says: *"Make the exponential smoothing forecaster handle missing values."*

- **Intent selection:** Outcome is "forecast runs on series with gaps and returns a sensible result." Readings: (a) interpolate gaps, (b) drop gaps, (c) raise a clear error. Chosen: (a) with linear interpolation, because it delivers the most and (b) and (c) are one-line fallbacks the user can request. Not chosen: (b), (c). Constraints: `python3 -m engine.tests.test_toolkit` must pass, no new deps.
- **Goal:** `python3 -m engine.tests.test_toolkit` exits 0 *and* a new test `test_missing_values_interpolated` exists and passes.
- **Loop:** write the failing test, implement, run, read. Attempt two fails on leading NaNs, so add an edge case and forward-fill the head. Attempt three passes. Run the full suite. Commit.
- **Report:** outcome, the test command output, and one decision the user might reverse: "chose linear interpolation; drop or error are trivial swaps."

Zero questions asked.

---

## Relationship to other skills

- `verification-before-completion` is the gate at the end of every loop. This skill adds the loop and the decision policy in front of it.
- `planning-with-files` supplies the on-disk memory pattern. This skill's `progress.md` is compatible with its `progress.md`.
- `executing-plans` batches work with review checkpoints. Use it when the user *asks* for checkpoints. Use this skill when they ask you not to.
- `prediction-toolkit` and `monte-carlo-predictor` are checks too: when the goal is a decision under uncertainty, the completion condition is "the simulation ran with ≥10,000 trials and the report includes P5/P50/P95."
- `autonomous-agents` explains why error rates compound. This skill's answer is short loops with a hard check after every step.

---

## Reference

`references/research-digest.md` summarises the sources this skill is built from: Anthropic's AI-native SDLC playbook and its security companion, the `/goal` command, the long-running-agent harness post, the building-effective-agents patterns, auto mode's classifier, and the intent-formalization research agenda.
