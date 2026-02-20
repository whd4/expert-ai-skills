# Agent-to-Agent Communication Protocol

**Purpose:** Agents share findings in real-time. When one agent learns something, others can adjust course — stop, pivot, or accelerate.

---

## The Communication Model

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR (Henry)                                  │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    MESSAGE BUS / SHARED CONTEXT                   │   │
│  │                                                                   │   │
│  │   All agents post findings here → All agents can read from here  │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│            │              │              │              │               │
│            ▼              ▼              ▼              ▼               │
│      ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐             │
│      │ Agent A │   │ Agent B │   │ Agent C │   │ Agent N │             │
│      │         │──▶│         │──▶│         │──▶│         │             │
│      │         │◀──│         │◀──│         │◀──│         │             │
│      └─────────┘   └─────────┘   └─────────┘   └─────────┘             │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

**Flow:**
1. Agent finds something significant
2. Agent posts to MESSAGE BUS
3. Orchestrator sees it immediately
4. Orchestrator broadcasts to other agents (or they read directly)
5. Other agents adjust course based on new info

---

## Message Types

### 1. DISCOVERY — "I found something"

```
MESSAGE TYPE: DISCOVERY
FROM: Agent A
TIMESTAMP: [time]
FINDING: [What was found]
CONFIDENCE: [0-100]
IMPACT: [How this affects the mission]
RECOMMENDED ACTION FOR OTHERS: [Stop / Adjust / Continue / Boost]
```

**Example:**
```
MESSAGE TYPE: DISCOVERY
FROM: Research Agent (market-analysis-001)
FINDING: The SaaS we're researching was acquired last week — no longer for sale
CONFIDENCE: 95%
IMPACT: Primary target is gone
RECOMMENDED ACTION FOR OTHERS:
  - Agent B (due diligence): STOP — target no longer valid
  - Agent C (alternatives): BOOST — we need backup options now
```

### 2. DEAD END — "This path doesn't work"

```
MESSAGE TYPE: DEAD_END
FROM: Agent B
TIMESTAMP: [time]
PATH TRIED: [What approach was attempted]
WHY IT FAILED: [Root cause]
WHAT WAS LEARNED: [Useful info despite failure]
AVOID: [What other agents should NOT try]
```

**Example:**
```
MESSAGE TYPE: DEAD_END
FROM: Build Agent (landing-page-002)
PATH TRIED: Using Framer for the landing page
WHY IT FAILED: Their API doesn't support our use case
WHAT WAS LEARNED: Framer only works for static sites
AVOID: Don't waste time on Framer for dynamic content
```

### 3. BREAKTHROUGH — "I solved a key piece"

```
MESSAGE TYPE: BREAKTHROUGH
FROM: Agent C
TIMESTAMP: [time]
SOLVED: [What was accomplished]
RESULT: [The output/answer]
OPENS UP: [What this enables for others]
NEXT: [What should happen next]
```

**Example:**
```
MESSAGE TYPE: BREAKTHROUGH
FROM: Negotiate Agent (vendor-003)
SOLVED: Got the vendor to agree to 40% discount
RESULT: Contract terms attached
OPENS UP: We now have budget for the premium tier
NEXT: Agent D can proceed with implementation using premium features
```

### 4. REQUEST — "I need help from another agent"

```
MESSAGE TYPE: REQUEST
FROM: Agent D
TO: [Specific agent or "any capable agent"]
NEED: [What's required]
BLOCKING: [What can't proceed without this]
PRIORITY: [Critical / High / Normal]
```

**Example:**
```
MESSAGE TYPE: REQUEST
FROM: Build Agent (api-integration-004)
TO: Research Agent (any)
NEED: Documentation for legacy API v2 endpoint
BLOCKING: Can't complete integration without this
PRIORITY: Critical
```

### 5. STATUS — "Here's where I am"

```
MESSAGE TYPE: STATUS
FROM: Agent E
TIMESTAMP: [time]
PROGRESS: [X%]
CURRENT FOCUS: [What I'm working on now]
BLOCKERS: [If any]
ETA: [Estimated completion]
```

---

## Orchestrator Actions on Messages

When the Orchestrator sees a message, it can:

| Message Type | Possible Actions |
|---|---|
| **DISCOVERY** | Broadcast to relevant agents, update shared context, adjust priorities |
| **DEAD_END** | Kill similar paths, redirect resources, log for future |
| **BREAKTHROUGH** | Unblock waiting agents, accelerate dependent work, celebrate |
| **REQUEST** | Dispatch new agent, redirect existing agent, answer directly |
| **STATUS** | Update dashboard, check for drift, intervene if needed |

---

## Real-Time Adjustments

### Scenario: One Agent Finds the Answer

```
BEFORE:
  Agent A: Searching approach X (50% done)
  Agent B: Searching approach Y (30% done)
  Agent C: Searching approach Z (70% done)

Agent C posts: BREAKTHROUGH — Found the answer via approach Z!

ORCHESTRATOR ACTION:
  → Agent A: STOP — answer found, no need to continue
  → Agent B: STOP — answer found, no need to continue
  → Agent C: COMPLETE — document and deliver result

AFTER:
  Agent A: Terminated (saved tokens)
  Agent B: Terminated (saved tokens)
  Agent C: Delivering final result
```

### Scenario: One Agent Hits Dead End, Learns Something Useful

```
BEFORE:
  Agent A: Trying API approach (in progress)
  Agent B: Trying scraping approach (in progress)
  Agent C: Trying manual approach (in progress)

Agent A posts: DEAD_END — API requires enterprise license we don't have
              LEARNED: API returns data format we need though

ORCHESTRATOR ACTION:
  → Agent A: Redirect to finding alternative data source with same format
  → Agent B: Continue — scraping might still work
  → Agent C: BOOST — if scraping fails, manual is our fallback

All agents now know: Don't waste time on the official API
```

### Scenario: Agent B's Finding Changes Agent A's Goal

```
BEFORE:
  Agent A: Researching competitors in market X
  Agent B: Analyzing our product-market fit

Agent B posts: DISCOVERY — Our best customers are actually in market Y, not X
              CONFIDENCE: 85%

ORCHESTRATOR ACTION:
  → Agent A: PIVOT — Stop researching market X, switch to market Y competitors
  → New shared context: Market Y is our real opportunity

Agent A's mission changed based on Agent B's finding
```

---

## Shared Context Structure

All agents have access to a shared context that updates in real-time:

```json
{
  "mission": "Original goal from user",
  "status": "in_progress",

  "discoveries": [
    {
      "timestamp": "...",
      "agent": "...",
      "finding": "...",
      "confidence": 85,
      "incorporated": true
    }
  ],

  "dead_ends": [
    {
      "path": "...",
      "reason": "...",
      "learned": "..."
    }
  ],

  "breakthroughs": [
    {
      "what": "...",
      "enables": "..."
    }
  ],

  "current_best_answer": {
    "content": "...",
    "confidence": 75,
    "from_agent": "...",
    "validated": false
  },

  "active_agents": [
    {
      "id": "...",
      "task": "...",
      "progress": 60,
      "status": "working"
    }
  ],

  "terminated_agents": [
    {
      "id": "...",
      "reason": "answer_found | dead_end | redirected | budget_exceeded"
    }
  ]
}
```

---

## Communication Rules

1. **Post immediately on significant findings** — Don't wait until done
2. **Read shared context before major decisions** — Check if anything changed
3. **Keep messages concise** — Just the essential info
4. **Tag relevance** — Help others know if it affects them
5. **No duplicate work** — Check if someone else already solved it
6. **Fail fast, share faster** — Dead ends are valuable, post them immediately

---

## Token Efficiency from Communication

This communication pattern SAVES tokens:

| Without Communication | With Communication |
|---|---|
| 5 agents work to completion | 1 agent finds answer, 4 stop early |
| Dead ends repeated | Dead ends shared, avoided by others |
| No cross-pollination | Findings boost other agents |
| 100% token spend | ~40-60% token spend for same result |

---

## Example: Full Mission with Communication

**User:** "Find the best CRM for a 10-person sales team under $500/mo"

**Spawn:**
```
Agent A: Research top-rated CRMs
Agent B: Research pricing and plans
Agent C: Check Reddit/forums for real user opinions
Agent D: Look for industry-specific options
```

**Message Flow:**

```
[T+2min] Agent B posts: DISCOVERY
  Finding: HubSpot free tier might be enough for 10 people
  Confidence: 70%
  Impact: Might not need to spend $500/mo at all

[T+3min] Orchestrator broadcasts:
  "Agent B found a potentially free option.
   Agent A: include free tiers in your research.
   Agent C: look for HubSpot experiences specifically."

[T+5min] Agent C posts: DISCOVERY
  Finding: Reddit users say HubSpot free is limited,
           frustrating after 6 months
  Confidence: 80%
  Impact: Free tier is a trap, need to plan for growth

[T+5min] Agent A posts: DEAD_END
  Path: Salesforce Essentials
  Why: Starts at $25/user = $250/mo but quickly scales to $75/user
  Learned: Avoid platforms with aggressive upsell pricing

[T+8min] Agent D posts: BREAKTHROUGH
  Found: Pipedrive at $14/user = $140/mo, highly rated for small teams
  Result: Matches budget, well-reviewed, no aggressive upsells
  Next: Need to verify it has features team needs

[T+10min] Orchestrator:
  → Agent A: STOP — we have a strong candidate
  → Agent C: PIVOT — look for Pipedrive reviews specifically
  → Agent B: Verify Pipedrive pricing and features
  → Agent D: COMPLETE — document your finding

[T+15min] Agent C posts: CONFIRMATION
  Pipedrive reviews on Reddit: 85% positive for small teams
  Confidence: 90%

[T+16min] MISSION COMPLETE
  Answer: Pipedrive at $140/mo
  Confidence: 88%
  Alternatives considered: HubSpot (free but limited),
                          Salesforce (too expensive)
```

Total tokens used: ~60% of what 4 independent agents would use.
Result: Better answer because agents learned from each other.
