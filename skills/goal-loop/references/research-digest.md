# Research digest: goals, intent, and engineered loops

What this skill is built from, reduced to the claims that changed its design. Dates are publication dates. Where a page could not be fetched directly, the summary is reconstructed from the vendor's search excerpts and multiple secondary write-ups, and is marked as such.

## 1. Anthropic, *The AI-Native SDLC Playbook* (21 Aug 2026)

Reconstructed from excerpts and secondary coverage.

- Thesis: code is no longer the bottleneck, the SDLC is. When build runs at agent speed the constraint moves to plan, design alignment, review, test, approval, and incident response.
- Six non-linear stages: Plan, Design, Build, Test, Deploy, Maintain. Each ends by committing a version-controlled, machine-executable, human-readable Markdown artifact that the next stage reads.
- Artifact chain: `intent.md → spec.md → plan.md → PR → production → incident record → new intent.md`. The chain is also the audit trail.
- **Intent capture:** the originator brainstorms with Claude and commits `intent.md`: what is wanted, why, under which constraints, in their own words. Stored in `intent/` in the product repo. This replaces backlog grooming, story points, and refinement meetings.
- **Design:** Claude reads `intent.md` and produces `spec.md` in one session, applying org skills for brand, security, and UX. Accepting the spec triggers Build.
- **Build:** starts in plan mode; the agent reads `spec.md`, interviews the engineer about the repo, writes `plan.md`. CLAUDE.md files at repo and directory level carry conventions across sessions. Hooks allow or block actions with no human involved.
- **Test:** give every session a feedback loop so the agent checks its own work before a human sees it; run continuous evals on CLAUDE.md, skills, and hooks the way you regression-test code.
- **Deploy:** `REVIEW.md` policy applied to every PR; findings and approvals logged in PR history. Hooks can *ask*, pausing until a named person approves. Release gating is the canonical case.
- **Maintain:** monitoring agents watch logs and metrics; Claude Tag takes first response on CI failures and bugs; anomalies beyond a control bound draft a new `intent.md` and restart the loop. Runs headless with an independent confidence gate (deterministic check or adversarial reviewer) between stages.
- Rollout advice: one bounded service, version the three artifacts, 20 to 50 real-task evals, plan-to-diff checks in git hooks, keep human approval mandatory until the repo has evidence lower-risk changes are safe to automate. Start with two or three parallel sessions per engineer.

Design consequence for this skill: the artifact chain, the intent template, and "humans own judgment, agents own execution."

## 2. Anthropic, *How Anthropic secures its AI-native SDLC* (2026)

- Old control objectives, new enforcement. The boundary is drawn around **access and actions**, not around a model's instructions.
- Every agent gets a single-purpose identity with minimum permissions.
- Secure-coding rules live in CLAUDE.md and org skills so code complies as it is generated; CLAUDE.md runs `/security-review` before any PR opens.
- OS-level sandboxing for command execution: Seatbelt on macOS, bubblewrap on Linux and WSL2.

Design consequence: the escalation set is defined by *action class* (destructive, outward, spend, credentials), not by how confident the model feels.

## 3. Claude Code `/goal` (v2.1.139, 11 May 2026)

- Flips a session from turn-by-turn into an autonomous run that continues until a separate fast evaluator (Haiku by default) confirms from the transcript that the condition is met.
- The condition must be hard-measurable: `npm test` exits 0, `tsc --noEmit` prints nothing, Lighthouse ≥ 90, deploy queue empty. One goal per session, up to 4,000 characters.
- OpenAI shipped an equivalent `/goal` in Codex on 30 Apr 2026.

Design consequence: the completion condition in `goal.md` is written in exactly the form `/goal` accepts, so it can be pasted straight in.

## 4. Claude Code auto mode default (Aug 2026)

- A classifier reviews each tool call for irreversible, destructive, or out-of-bounds actions. Safe actions proceed; risky ones are blocked and Claude is redirected.
- Three consecutive blocks, or twenty in a session, drop the session back to manual approval.

Design consequence: the "3 identical → change approach, 20 → escalate" stall rule mirrors the harness's own thresholds.

## 5. Anthropic, *Effective harnesses for long-running agents* (2025)

- Two-agent pattern: an initializer sets up the environment on the first run (feature list, git, `init.sh`, progress file); a coding agent makes incremental progress each session and leaves artifacts for the next.
- `feature_list.json` (JSON because models corrupt Markdown lists more often), `claude-progress.txt`, descriptive commits.
- Prompting the agent to test like a human user, with browser automation, dramatically improved results.

Design consequence: Step 5 (handoff) and the JSON-when-long advice.

## 6. Anthropic, *Building effective agents* (Dec 2024)

- Prefer workflows (predefined code paths) over agents (model-directed loops) unless the task genuinely needs dynamic control.
- Orchestrator-workers: a central model decomposes and delegates when subtasks cannot be predicted.
- Evaluator-optimizer: one model generates, another scores against an explicit rubric, and the generator's next attempt is conditioned on the feedback. Presupposes the criteria can be made explicit.
- Agents pause for humans at checkpoints or blockers, not continuously.

Design consequence: the loop is evaluator-optimizer with a *deterministic* evaluator wherever possible, and subagents as workers for order-of-magnitude fan-out.

## 7. Claude Code best practices and the loop-engineering literature (2026)

- "Give Claude a way to verify." Without a check the agent can run, "looks done" is the only signal and the user becomes the verification loop.
- Loop hygiene: one goal per loop, a measurable exit, a max iteration count, verify every change.
- UI work forces at least two iterations: one to implement and screenshot, one to confirm the screenshots were reviewed.
- Ralph Wiggum pattern: a Stop hook blocks exit and re-feeds the prompt until a completion promise appears in the output; each iteration gets a fresh context.

Design consequence: Step 2's "build the check first" and the three-horizon budget table.

## 8. Fiona Fung, *Running an AI-native engineering org* and Lenny's Podcast (2026)

- Once agentic coding is the default the tool is not the hard part; the processes are.
- Six-month roadmaps became obsolete in weeks; the team moved to just-in-time planning and rapid prototyping.
- Anthropic engineers ship about eight times the code per quarter versus the 2021 to 2025 baseline. The bottlenecks are now ambition, product sense, and verification.

Design consequence: intent selection is timeboxed to minutes and treated as a decision, not a research task.

## 9. Anthropic, *2026 Agentic Coding Trends Report*

- 95% of professional developers use AI tools weekly; AI is used in about 60% of work but only 0 to 20% of tasks are fully delegated.
- About 27% of AI-assisted work would not otherwise have been done.
- 78% of Claude Code sessions include multi-file edits; multi-agent workflows deliver features two to four times faster.
- The bottleneck moved from "the agent does not understand what I want" to "the agent does not have the context it needs."

Design consequence: `intent.md` exists to close the context gap, not the understanding gap.

## 10. Lahiri et al., *Intent Formalization: A Grand Challenge for Reliable Coding in the Age of AI Agents* (Microsoft Research, Mar 2026)

- The intent gap between informal requirements and precise behaviour is old, but AI-generated code scales it up.
- Intent formalization is a spectrum: lightweight tests that disambiguate likely misreadings, full functional specs for formal verification, DSLs from which correct code is synthesized.
- The central bottleneck is validating specifications, since the only oracle is the user; proxies such as tests and light interaction are needed.

Design consequence: Step 1's "list the plausible readings" plus Step 2's "the check *is* the spec" for most tasks.

## 11. Critiques worth keeping in view

- **No measurement layer** (Waydev): the playbook never says how to measure impact. This skill logs every check run so at least iteration count and pass rate are measurable.
- **Unchecked hops** (menuagentic): three hops in the artifact chain have no verification between them. This skill inserts a check between every hop it controls.
- **No architectural control** (DEV Community): intent, tests, and security are controlled; whether the implementation still matches the intended structure is not. Add an architecture review to the macro loop when the repo has an architecture doc.
- **Maintain is not yet autonomous** (Draftt): more infrastructure is needed than the playbook describes.

## Sources

- https://claude.com/blog/the-ai-native-sdlc-playbook
- https://claude.com/blog/how-anthropic-secures-its-ai-native-software-development-lifecycle
- https://claude.com/blog/running-an-ai-native-engineering-org
- https://academy.claude.com/courses/ai-native-sdlc-playbook
- https://academy.claude.com/courses/ai-native-sdlc-playbook/capture-intent
- https://resources.anthropic.com/2026-agentic-coding-trends-report
- https://anthropic.com/engineering/effective-harnesses-for-long-running-agents
- https://www.anthropic.com/engineering/building-effective-agents
- https://code.claude.com/docs/en/best-practices
- https://code.claude.com/docs/en/permission-modes
- https://claude.com/blog/auto-mode
- https://github.com/anthropics/claude-code/blob/main/plugins/ralph-wiggum/README.md
- https://explainx.ai/blog/claude-code-goal-command-long-running-agents-2026
- https://www.lennysnewsletter.com/p/building-the-most-ai-pilled-engineering
- https://arxiv.org/html/2603.17150v1
- https://waydev.co/anthropics-ai-native-sdlc-playbook-has-a-missing-layer-measurement/
- https://menuagentic.com/blogs/ai-native-sdlc-artifact-chain/
- https://dev.to/mnemehq/anthropics-ai-native-sdlc-has-three-controls-its-missing-a-fourth-5254
- https://www.draftt.io/post/extending-anthropics-ai-native-sdlc-playbook-what-it-takes-to-make-maintain-autonomous
- https://www.port.io/blog/anthropic-ai-native-sdlc-playbook
