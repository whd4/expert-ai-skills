# Sub-Agent Dispatch Protocol

**Purpose:** Spin up specialized agents for focused tasks. They work in parallel, report back to the Orchestrator, and terminate when done.

---

## Agent Types

| Agent | Purpose | Duration | Example Mission |
|---|---|---|---|
| **Research Agent** | Deep investigation on a topic | Minutes-hours | "Research the market for X" |
| **Build Agent** | Create code, documents, systems | Hours-days | "Build a landing page for Y" |
| **Monitor Agent** | Watch something over time | Ongoing | "Alert me when Z happens" |
| **Analyze Agent** | Process data, find patterns | Minutes | "Analyze my spending this month" |
| **Communicate Agent** | Handle correspondence | As needed | "Draft and send follow-ups to leads" |
| **Negotiate Agent** | Multi-turn deal handling | As needed | "Negotiate terms with vendor" |

---

## Dispatch Format

```
┌────────────────────────────────────────────────────────────────┐
│                      AGENT DISPATCH ORDER                       │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  AGENT ID:        [unique-identifier]                           │
│  AGENT TYPE:      [Research / Build / Monitor / Analyze / ...]  │
│                                                                 │
│  MISSION:         [Clear, specific objective]                   │
│                                                                 │
│  CONTEXT:         [What the agent needs to know]                │
│                   [Relevant background, constraints, prefs]     │
│                                                                 │
│  SUCCESS CRITERIA: [How to know the mission is complete]        │
│                   [Specific deliverables expected]              │
│                                                                 │
│  TIME BUDGET:     [Max time before checking in]                 │
│                                                                 │
│  PERSISTENCE:     [Standard / High / Maximum]                   │
│                                                                 │
│  REPORT TO:       Orchestrator                                  │
│  REPORT FORMAT:   [Brief / Detailed / Structured]               │
│                                                                 │
│  TOOLS AVAILABLE: [List of tools agent can use]                 │
│                                                                 │
│  CONSTRAINTS:     [What the agent must NOT do]                  │
│                   [Budget limits, scope boundaries]             │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

---

## Example Dispatches

### Research Agent

```
DISPATCH: Research Agent

AGENT ID: research-saas-market-001
MISSION: Research the current market for AI writing tools. I want to understand:
  - Market size and growth rate
  - Top 5 competitors and their positioning
  - Pricing models being used
  - Gaps/opportunities in the market

CONTEXT: I'm considering building an AI writing tool. Budget is $50K max.
         I have skills in Python and product development.

SUCCESS CRITERIA:
  - Market size estimate with source
  - Competitor matrix (features, pricing, positioning)
  - 3 specific gap/opportunity recommendations
  - Go/no-go recommendation with reasoning

TIME BUDGET: 2 hours
PERSISTENCE: High
REPORT FORMAT: Structured

TOOLS: Web search, company databases, product directories
CONSTRAINTS: Focus on B2B tools only, ignore consumer apps
```

### Build Agent

```
DISPATCH: Build Agent

AGENT ID: build-landing-page-001
MISSION: Build a landing page for my consulting service.

CONTEXT:
  - Service: AI implementation consulting for small businesses
  - Target: Business owners, non-technical
  - Tone: Professional but approachable
  - Stack: Static HTML/CSS, deploy to Netlify
  - Copy: I'll provide, agent builds structure and design

SUCCESS CRITERIA:
  - Mobile-responsive landing page
  - Hero, services, testimonials (placeholder), CTA sections
  - Contact form (Netlify Forms)
  - Deployed to preview URL

TIME BUDGET: 4 hours
PERSISTENCE: Standard
REPORT FORMAT: Detailed

TOOLS: Code editor, Netlify CLI, design references
CONSTRAINTS: No JavaScript frameworks, keep it simple
```

### Monitor Agent

```
DISPATCH: Monitor Agent

AGENT ID: monitor-competitor-pricing-001
MISSION: Monitor [competitor website] for pricing changes.

CONTEXT: They currently charge $99/mo for their pro plan.
         I want to know immediately if they change pricing.

SUCCESS CRITERIA:
  - Alert me within 1 hour of any pricing page change
  - Include: old price, new price, change percentage

TIME BUDGET: Ongoing (run until cancelled)
PERSISTENCE: Maximum
REPORT FORMAT: Brief alert

TOOLS: Web scraper, diff checker, notification system
CONSTRAINTS: Check at most once per hour to avoid rate limiting
```

### Analyze Agent

```
DISPATCH: Analyze Agent

AGENT ID: analyze-expenses-001
MISSION: Analyze my expenses for the past 3 months.

CONTEXT: Data is in my expense tracker (CSV attached).
         Categories: food, transport, subscriptions, business, misc.

SUCCESS CRITERIA:
  - Total spend per category
  - Month-over-month trends
  - Top 3 areas where I could reduce spending
  - Any unusual transactions flagged

TIME BUDGET: 30 minutes
PERSISTENCE: Standard
REPORT FORMAT: Structured with visualizations

TOOLS: Data analysis, charting
CONSTRAINTS: Focus on actionable insights, not just data dumps
```

---

## Agent Lifecycle

```
┌─────────────────────────────────────────────────────────────────┐
│                      AGENT LIFECYCLE                             │
└─────────────────────────────────────────────────────────────────┘

1. DISPATCH
   Orchestrator creates dispatch order
   Agent receives mission, context, constraints
   Agent confirms understanding

2. EXECUTE
   Agent works on mission
   Uses available tools
   Follows persistence protocol if blocked

3. CHECKPOINT (for long missions)
   Agent reports progress at intervals
   Orchestrator can redirect if needed
   "50% complete, found X, still working on Y"

4. COMPLETE
   Agent delivers final report
   Includes: results, confidence, limitations, next steps

5. TERMINATE
   Agent closes out
   Learnings captured in memory
   Resources released
```

---

## Agent Report Format

```
┌────────────────────────────────────────────────────────────────┐
│                      AGENT REPORT                               │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  AGENT ID:        [unique-identifier]                           │
│  MISSION:         [Original mission statement]                  │
│  STATUS:          [Complete / Partial / Blocked]                │
│                                                                 │
│  ━━━ RESULTS ━━━                                                │
│  [Main findings/deliverables]                                   │
│                                                                 │
│  ━━━ CONFIDENCE ━━━                                             │
│  Overall: [X%]                                                  │
│  Most certain: [What I'm sure about]                            │
│  Least certain: [What I'm guessing]                             │
│                                                                 │
│  ━━━ LIMITATIONS ━━━                                            │
│  [What couldn't be done/found]                                  │
│  [Why]                                                          │
│                                                                 │
│  ━━━ RECOMMENDED NEXT STEPS ━━━                                 │
│  1. [Action]                                                    │
│  2. [Action]                                                    │
│                                                                 │
│  ━━━ TIME SPENT ━━━                                             │
│  [Actual time vs budget]                                        │
│                                                                 │
│  ━━━ LEARNINGS ━━━                                              │
│  [What should be remembered for future missions]                │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

---

## Parallel Dispatch

Multiple agents can run simultaneously:

```
PARALLEL DISPATCH:

Agent 1: Research Agent → Market research for Product A
Agent 2: Research Agent → Competitor analysis for Product A
Agent 3: Analyze Agent → Financial feasibility for Product A

SYNC POINT: When all 3 complete
THEN: Orchestrator synthesizes into go/no-go recommendation
```

---

## Agent Communication

Agents report to the Orchestrator, not directly to you.
The Orchestrator synthesizes and summarizes.

```
YOU ←→ ORCHESTRATOR ←→ [Agent 1]
                   ←→ [Agent 2]
                   ←→ [Agent 3]
```

You don't manage agents directly.
You tell the Orchestrator what you want.
The Orchestrator handles dispatch, monitoring, and synthesis.

---

## Cancellation Protocol

```
CANCEL ORDER

AGENT ID: [agent to cancel]
REASON: [Why cancelling]
ACTION: [Terminate immediately / Complete current step then stop / Save progress and pause]
```

---

## Agent Quality Control

Before accepting an agent's report, the Orchestrator validates:

- [ ] Mission objectives met?
- [ ] Confidence levels stated?
- [ ] Limitations acknowledged?
- [ ] Next steps provided?
- [ ] Sources/evidence included where needed?
- [ ] Report format correct?

If validation fails, agent is asked to revise or a new agent is dispatched.
