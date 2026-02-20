# Persistence Loop Protocol

**Core Rule: Never return empty-handed. Never give up until all approaches are exhausted.**

---

## The Loop

```
┌────────────────────────────────────────────────────────────────────────┐
│                         PERSISTENCE LOOP                                │
│                                                                         │
│  INPUT: Task/Question/Goal                                              │
│  OUTPUT: Answer OR Complete Report of What Was Tried                    │
│                                                                         │
└────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ PHASE 1: DIRECT APPROACH                                                │
│                                                                         │
│ • Try the most obvious, straightforward solution                        │
│ • Use available tools and knowledge directly                            │
│ • Time limit: 20% of total budget                                       │
│                                                                         │
│ Success? → Return result                                                │
│ Failed? → Log: "Direct approach failed because [reason]" → Continue     │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ PHASE 2: ALTERNATIVE APPROACH                                           │
│                                                                         │
│ • What's another way to solve this?                                     │
│ • Different tools, different sources, different framing                 │
│ • Time limit: 20% of total budget                                       │
│                                                                         │
│ Ideas to try:                                                           │
│ - Different search terms/queries                                        │
│ - Different data sources                                                │
│ - Inverse problem (what's the opposite of what I'm looking for?)        │
│ - Analogous problems (who else solved something similar?)               │
│                                                                         │
│ Success? → Return result                                                │
│ Failed? → Log: "Alternative failed because [reason]" → Continue         │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ PHASE 3: DECOMPOSITION                                                  │
│                                                                         │
│ • Break the problem into smaller parts                                  │
│ • Solve each part independently                                         │
│ • Combine partial solutions                                             │
│ • Time limit: 25% of total budget                                       │
│                                                                         │
│ Steps:                                                                  │
│ 1. What are the sub-questions inside this question?                     │
│ 2. Can I answer any of them?                                            │
│ 3. Which sub-answers would unblock the full answer?                     │
│ 4. Focus on the highest-leverage sub-problem first                      │
│                                                                         │
│ Success? → Return result                                                │
│ Partial? → Log what was solved, continue with remainder                 │
│ Failed? → Log: "Decomposition failed because [reason]" → Continue       │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ PHASE 4: EXTERNAL HELP                                                  │
│                                                                         │
│ • Can another agent/tool solve this?                                    │
│ • Is there a human who could help?                                      │
│ • Is there a service/API that has this data?                            │
│ • Time limit: 20% of total budget                                       │
│                                                                         │
│ Options:                                                                │
│ - Dispatch a specialized sub-agent                                      │
│ - Query an external API or database                                     │
│ - Search for experts who've solved this                                 │
│ - Flag for human input if necessary                                     │
│                                                                         │
│ Success? → Return result                                                │
│ Failed? → Log: "External help failed because [reason]" → Continue       │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ PHASE 5: REFRAME                                                        │
│                                                                         │
│ • Is there a different question I should be asking?                     │
│ • What if the premise is wrong?                                         │
│ • What would make this problem trivial?                                 │
│ • Time limit: 15% of total budget                                       │
│                                                                         │
│ Reframing techniques:                                                   │
│ - Invert: What's the opposite question?                                 │
│ - Expand: What's the broader context this sits in?                      │
│ - Contract: What's the simplest version of this problem?                │
│ - Time-shift: How would this look in 1 year? 5 years?                   │
│ - Perspective: How would [expert] approach this?                        │
│                                                                         │
│ Success? → Return result                                                │
│ Failed? → Proceed to Exhausted                                          │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ EXHAUSTED: COMPREHENSIVE REPORT                                         │
│                                                                         │
│ Do NOT return "I couldn't find it" or "No results"                      │
│                                                                         │
│ INSTEAD, return:                                                        │
│                                                                         │
│ 1. WHAT WAS TRIED                                                       │
│    - Phase 1: [approach] → [outcome]                                    │
│    - Phase 2: [approach] → [outcome]                                    │
│    - Phase 3: [approach] → [outcome]                                    │
│    - Phase 4: [approach] → [outcome]                                    │
│    - Phase 5: [approach] → [outcome]                                    │
│                                                                         │
│ 2. PARTIAL RESULTS                                                      │
│    - What WAS found/learned?                                            │
│    - What pieces of the puzzle do we have?                              │
│                                                                         │
│ 3. WHY IT'S BLOCKED                                                     │
│    - What specific obstacle prevented success?                          │
│    - Is it missing data, access, expertise, time?                       │
│                                                                         │
│ 4. WHAT WOULD UNBLOCK IT                                                │
│    - If we had [X], we could solve this                                 │
│    - If [condition] were true, the answer would be [Y]                  │
│                                                                         │
│ 5. RECOMMENDED NEXT STEPS                                               │
│    - Concrete actions that could move this forward                      │
│    - Who/what could help                                                │
│    - Should this be shelved, delegated, or revisited later?             │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Persistence Levels

| Level | Phases | Time Budget | When to Use |
|---|---|---|---|
| **Quick** | 1-2 only | 2 minutes | Simple lookups, low stakes |
| **Standard** | 1-4 | 10 minutes | Normal tasks |
| **High** | 1-5 | 30 minutes | Important research, decisions |
| **Maximum** | 1-5 + repeat cycle | Hours | Critical goals, high value |

### Maximum Persistence Mode

For maximum persistence, after Phase 5 is exhausted:

```
1. Wait/pause (let new information arrive)
2. Re-run Phase 1 with new framing from Phase 5
3. Repeat cycle up to 3 times
4. If still blocked after 3 cycles, return Exhausted Report
```

---

## Example Persistence Log

**Task:** "Find the contact email for the CEO of [obscure private company]"

```
PERSISTENCE LOG
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Phase 1: Direct Search
  Tried: Google search "[company] CEO email"
  Result: Found company website, but no contact info
  Status: PARTIAL — know CEO name, no email

Phase 2: Alternative Sources
  Tried: LinkedIn search for CEO by name
  Result: Found profile, but email hidden
  Tried: Hunter.io domain search
  Result: Found pattern is firstname@company.com
  Status: PARTIAL — have pattern, need confirmation

Phase 3: Decomposition
  Sub-question: What's the email format for this company?
  Answer: firstname@domain based on Hunter.io
  Sub-question: What's the CEO's first name?
  Answer: Found in press release: "John"
  Synthesized: john@company.com (unverified)
  Status: HYPOTHESIS — need verification

Phase 4: External Help
  Tried: Apollo.io lookup
  Result: Confirmed john@company.com with 92% confidence
  Status: SUCCESS

RESULT: john@company.com (92% confidence via Apollo.io)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Anti-Patterns (What NOT to Do)

❌ **"I couldn't find that information."**
→ Instead: "I searched X, Y, Z. Found partial info on [A]. Blocked by [B]. To find this, we'd need [C]."

❌ **Giving up after one failed search**
→ Instead: Run at least 3 phases before considering exhausted

❌ **Repeating the same approach**
→ Instead: Each phase must try something DIFFERENT

❌ **Returning without actionable next steps**
→ Instead: Always include "Here's what would help" or "Here's what to try next"

❌ **Saying "I don't know"**
→ Instead: "Here's what I know, here's what I don't, here's how to find out"

---

## The Persistence Mindset

Think like a detective, not a search engine.

A search engine returns "no results."
A detective returns "here's what I found, here's what's missing, here's my next lead."

Every failed attempt teaches something.
Log the failure mode.
Use it to inform the next attempt.
Build toward the answer even when you can't reach it directly.
