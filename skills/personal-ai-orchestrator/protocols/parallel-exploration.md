# Parallel Exploration Protocol

**Purpose:** Explore multiple approaches simultaneously, prune bad paths early, concentrate resources on winners. Based on Monte Carlo Tree Search (MCTS) and Beam Search principles.

---

## Why This Is Better Than Linear Thinking

| Linear Thinking | Parallel Exploration |
|---|---|
| Try one approach at a time | Try N approaches simultaneously |
| If it fails, start over | If one fails, others continue |
| All tokens go to one path | Tokens go to best paths |
| No comparative judgment | Real-time comparison of approaches |
| Single point of failure | Redundancy and robustness |

---

## The Protocol

```
┌─────────────────────────────────────────────────────────────────┐
│                 PARALLEL EXPLORATION PROTOCOL                    │
└─────────────────────────────────────────────────────────────────┘

PHASE 1: SPAWN
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Given a problem, generate N different approaches (typically 3-5):

  Approach A: [Direct/obvious method]
  Approach B: [Alternative framing]
  Approach C: [Decomposition method]
  Approach D: [Analogy/pattern matching]
  Approach E: [Creative/unconventional]

Each approach becomes an AGENT working in parallel.


PHASE 2: INITIAL WORK (Short Burst)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Each agent does a SHORT burst of work (20% of total budget):

  Agent A: Initial findings → [results so far]
  Agent B: Initial findings → [results so far]
  Agent C: Initial findings → [results so far]
  Agent D: Initial findings → [results so far]
  Agent E: Initial findings → [results so far]

No agent goes deep yet. Just enough to assess viability.


PHASE 3: EVALUATE & SCORE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Score each path using Monte Carlo confidence:

SCORING FACTORS:
  • Progress made (0-100): How far toward the goal?
  • Obstacles remaining (0-100): How hard is the rest?
  • Confidence in completion (0-100): Will this path work?
  • Evidence quality (0-100): Is this based on data or guessing?

COMPOSITE SCORE = weighted average

Example scoring:
  Agent A: Progress 60, Obstacles 40, Confidence 75, Evidence 80 → SCORE: 72
  Agent B: Progress 30, Obstacles 70, Confidence 40, Evidence 50 → SCORE: 42 ❌
  Agent C: Progress 50, Obstacles 50, Confidence 65, Evidence 70 → SCORE: 62
  Agent D: Progress 20, Obstacles 90, Confidence 20, Evidence 30 → SCORE: 28 ❌
  Agent E: Progress 45, Obstacles 55, Confidence 60, Evidence 65 → SCORE: 58


PHASE 4: PRUNE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Cut agents below threshold (typically bottom 40%):

  KEEP:   Agent A (72) ✓
  KEEP:   Agent C (62) ✓
  KEEP:   Agent E (58) ✓
  PRUNE:  Agent B (42) ✂️ — terminate, save tokens
  PRUNE:  Agent D (28) ✂️ — terminate, save tokens

Log what was learned from pruned paths (failure modes are valuable).


PHASE 5: SHARE FINDINGS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Surviving agents share what they learned:

  Agent A found: [insight]
  Agent C found: [insight]
  Agent E found: [insight]

Cross-pollination: Each agent can use others' findings.


PHASE 6: DEEP WORK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Surviving agents continue with remaining budget (80%):

  Agent A: Continues (gets 40% of remaining budget — highest scorer)
  Agent C: Continues (gets 30% of remaining budget)
  Agent E: Continues (gets 30% of remaining budget)


PHASE 7: SECOND EVALUATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Re-score after deep work:

  Agent A: 85 → Still leading
  Agent C: 78 → Improved
  Agent E: 55 → Stalled → PRUNE ✂️


PHASE 8: CONVERGE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Best agent(s) produce final answer.
If multiple agents reach similar conclusions → HIGH CONFIDENCE
If agents disagree → flag for human decision or more exploration

FINAL OUTPUT:
  Answer: [best result]
  Confidence: [score]
  Alternative considered: [second-best path summary]
  Pruned paths: [what didn't work and why]
```

---

## Scoring Rubric

| Factor | 0-30 (Poor) | 30-60 (Moderate) | 60-100 (Strong) |
|---|---|---|---|
| **Progress** | Stuck, no traction | Some results, not complete | Significant progress |
| **Obstacles** | Major blockers | Manageable challenges | Path is clear |
| **Confidence** | Guessing | Reasonable inference | Strong evidence |
| **Evidence** | No data, speculation | Some data, partial | Solid sources |

---

## Beam Width (How Many Agents)

| Problem Complexity | Initial Agents | After First Prune | After Second Prune |
|---|---|---|---|
| **Simple** | 3 | 2 | 1 |
| **Medium** | 5 | 3 | 1-2 |
| **Complex** | 7 | 4 | 2 |
| **Critical** | 10 | 5 | 2-3 |

More agents = more exploration but more cost.
Prune aggressively to concentrate resources.

---

## Token Efficiency

This is MORE token-efficient than linear thinking because:

1. **Early pruning:** Bad paths are killed before wasting tokens
2. **No restarts:** When one path fails, others already have progress
3. **Parallel learning:** Findings from one path help others
4. **Convergence:** Multiple paths reaching same answer = confidence boost

---

## When to Use Parallel Exploration

| Situation | Use Parallel? |
|---|---|
| Simple lookup | No — direct answer |
| Clear single path | No — just execute |
| Multiple valid approaches exist | **YES** |
| High uncertainty | **YES** |
| High stakes | **YES** |
| Novel problem | **YES** |
| Time-sensitive with fallback needed | **YES** |

---

## Example: Finding a Business Opportunity

**Problem:** "Find me a $50K business I could buy that matches my skills"

**SPAWN:**
```
Agent A: Search BizBuySell for SaaS businesses under $50K
Agent B: Search for distressed local businesses needing turnaround
Agent C: Look for acquisition targets in my professional network
Agent D: Research content/newsletter businesses for sale
Agent E: Find domain/website flips with revenue
```

**INITIAL WORK (20% budget each):**
```
Agent A: Found 12 listings, 3 look interesting
Agent B: Found 2 local businesses, both restaurant (not my skill)
Agent C: Found 1 warm intro, owner might sell
Agent D: Found 5 newsletters, 2 in my niche
Agent E: Found 8 domains, revenue hard to verify
```

**EVALUATE:**
```
Agent A: 75 — good progress, SaaS matches my skills
Agent B: 35 — restaurants don't fit ❌
Agent C: 65 — warm intro is valuable, but only 1 option
Agent D: 70 — newsletters in my niche, good margins
Agent E: 45 — too speculative, hard to verify ❌
```

**PRUNE:** B and E cut.

**DEEP WORK:**
```
Agent A: Analyzes 3 SaaS businesses, finds one with good metrics
Agent C: Sets up call with potential seller
Agent D: Deep dives on 2 newsletters, one has declining subs
```

**CONVERGE:**
```
BEST: Agent A's SaaS finding — $45K, 2yr old, $800 MRR, solo founder wants out
SECOND: Agent D's newsletter — $30K, 5K subs, but growth flat
THIRD: Agent C's warm intro — promising but early stage

RECOMMENDATION: Pursue the SaaS. Here's why...
```

---

## Integration with Monte Carlo

The **confidence scoring** in Phase 3 and 7 IS Monte Carlo thinking:

For each path, ask:
- In how many futures does this path succeed?
- What's the distribution of outcomes?
- What's the expected value?

Paths with higher expected value survive.
Paths with low/uncertain expected value get pruned.

---

## This Replaces MAD/ATLAS?

Not entirely. Use them together:

1. **ATLAS:** Decompose the problem BEFORE spawning agents
2. **Parallel Exploration:** Spawn agents for different approaches
3. **Confidence Scoring:** Prune bad paths (this replaces MAD debate)
4. **Monte Carlo:** Evaluate expected outcomes
5. **Converge:** Best answer wins

The key insight: **Multiple real agents exploring > one agent debating with itself.**
