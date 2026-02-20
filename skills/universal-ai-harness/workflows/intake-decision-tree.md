# INTAKE Layer: Decision Tree

Use this decision tree to classify any incoming request and determine the appropriate depth and reasoning mode.

---

## Step 1: Is This a Question or a Task?

```
Request comes in
      │
      ├─── QUESTION (seeking information)
      │         │
      │         ├─── Factual lookup? → MINIMAL depth, direct retrieval
      │         │
      │         ├─── Explanation needed? → LIGHT depth, Chain-of-Thought
      │         │
      │         └─── Research required? → FULL depth, ReAct (iterative search)
      │
      └─── TASK (seeking action or creation)
                │
                ├─── Debugging? → MEDIUM depth, ReAct
                │
                ├─── Implementation? → FULL depth, Spec-first → Tree-of-Thought
                │
                ├─── Architecture? → FULL+ depth, Multi-Agent Deliberation
                │
                └─── Decision? → FULL depth, Monte Carlo + MAD
```

---

## Step 2: Determine Spec Requirement

| If Task Type Is... | Spec Required? | Spec Format |
|---|---|---|
| Factual query | No | — |
| Explanation | No | — |
| Simple debugging | No | — |
| Complex debugging | Light | Hypothesis document |
| Small implementation (<30 min) | Light | Brief task spec |
| Medium implementation (30min–4hr) | Yes | PRD + task breakdown |
| Large implementation (>4hr) | Yes | Full PRD + Architecture + Tasks |
| Architecture design | Yes | Architecture Decision Record (ADR) |
| Technology decision | Yes | Decision spec with criteria matrix |
| Strategic decision | Yes | Full decision spec + Monte Carlo |

---

## Step 3: Select Reasoning Mode

### Chain-of-Thought (CoT)
**Use when:** Linear reasoning leads to the answer. No external actions needed.

```
Good for:
• Explaining concepts
• Analyzing code
• Working through logic problems
• Simple planning

Example trigger phrases:
• "Explain..."
• "Why does..."
• "Walk me through..."
• "What's the logic behind..."
```

### ReAct (Reasoning + Acting)
**Use when:** You need to gather information, test hypotheses, or interact with systems.

```
Good for:
• Debugging (observe → hypothesize → test)
• Research (search → read → synthesize)
• Exploration (try → learn → adjust)
• Integration (call → observe → adapt)

Example trigger phrases:
• "Find out why..."
• "Debug this..."
• "Research..."
• "Figure out how to..."
```

### Tree-of-Thought (ToT)
**Use when:** Multiple valid approaches exist and you need to explore them.

```
Good for:
• Implementation with design choices
• Optimization problems
• Creative solutions
• Algorithm design

Example trigger phrases:
• "What's the best way to..."
• "Design a solution for..."
• "Implement [complex feature]..."
• "Optimize..."
```

### Multi-Agent Deliberation
**Use when:** High-stakes decisions that benefit from multiple perspectives.

```
Good for:
• Architecture decisions
• Technology stack choices
• Strategic direction
• Trade-off heavy problems

Example trigger phrases:
• "Should we..."
• "Architect the system for..."
• "What's the right approach for..."
• "Evaluate whether..."

Personas to invoke:
• Architect (technical correctness)
• Product Manager (user/business value)
• Security Engineer (risk and protection)
• Pragmatist (what's actually achievable)
• Devil's Advocate (what could go wrong)
```

---

## Step 4: Check Memory

Before reasoning, always query:

```
MEMORY CHECKLIST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
□ Have I solved a similar problem before?
  → Check episodic_memory.sessions

□ Do I have domain knowledge that applies?
  → Check semantic_memory.domain_knowledge

□ Is there a known workflow for this task type?
  → Check procedural_memory.workflows

□ Have I failed at something similar before?
  → Check outcome_memory.failures

□ Are there relevant pending validations?
  → Check outcome_memory.pending_validation
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Quick Reference: INTAKE Output

After running through the decision tree, output:

```
INTAKE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Request Type:    [Question | Task]
Task Type:       [Factual | Explanation | Debugging | Implementation | Architecture | Decision | Research]
Depth:           [Minimal | Light | Medium | Full | Full+]
Reasoning Mode:  [Direct | CoT | ReAct | ToT | Multi-Agent]
Spec Required:   [No | Light | Full]
Memory Query:    [What to look up before proceeding]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Then proceed to the appropriate layer.
