# Deep Confidence: Full Atlas Mode Example

## User Request
"I'm building a real-time collaboration feature (like Google Docs live cursors + edits) for my existing Next.js SaaS app. Should I use WebSockets, Server-Sent Events, or a third-party service like Liveblocks or Ably? I have 2 developers and about 6 weeks."

---

# Deep Confidence Response: Real-Time Collaboration Architecture

## ATLAS Summary

- **Goal:** Choose the right real-time sync architecture for collaborative editing in a Next.js SaaS — decision must be implementable by 2 devs in 6 weeks.
- **Key constraints:**
  - 2 developers (limited bandwidth for complex infrastructure)
  - 6-week deadline (no room for deep custom infrastructure work)
  - Existing Next.js app (must integrate cleanly)
  - "Google Docs style" (live cursors + concurrent edits = conflict resolution required)
- **Critical assumptions:**
  - I'm assuming this is cloud-hosted (Vercel or similar), not self-hosted
  - I'm assuming user count is <10K concurrent at launch
  - I'm assuming conflict resolution (CRDT/OT) is a requirement, not optional
  - I'm assuming the team has no prior WebSocket production experience

---

## MAD Debate

**Best approach:** Use Liveblocks (managed third-party service).

**Strongest counterargument (The Skeptic):**
"Third-party services create lock-in and add ongoing costs. WebSockets give full control and are free to run. A good engineer should be able to implement WebSockets in 6 weeks. You're paying Liveblocks $99-$500/month forever when the underlying technology is not that hard."

**Strongest counterargument (The User):**
"But I need conflict resolution — what happens when two users edit the same paragraph simultaneously? WebSockets just transport data; they don't solve the hard problem of concurrent edits. CRDT implementation is a research-level problem."

**Strongest counterargument (The Future Self):**
"In 6 months, if Liveblocks raises prices or changes their API, we're stuck refactoring. That's a real risk."

**Verdict — Liveblocks holds, with nuance:**

The Skeptic is right that WebSockets are free and give full control. But the User's point is more important: **the hard problem isn't transport, it's conflict resolution.** Building a production-grade CRDT or OT implementation in 6 weeks with 2 developers who have no prior experience with it is extremely high-risk. Liveblocks solves this as a managed service.

The lock-in risk (Future Self) is real but manageable: Liveblocks uses a standard Yjs CRDT under the hood. If you ever need to migrate, the data model is portable.

**Updated recommendation:** Liveblocks for the collaboration layer, WebSockets (via Liveblocks' abstraction) for transport.

---

## Scenario Outlook (Monte Carlo)

**S1 — Best Case (10%):** Team ships in 4 weeks, Liveblocks integration is smooth, users love the feature, collaboration becomes a key differentiator.

**S2 — Optimistic (25%):** Ships at 6 weeks as planned. A few edge cases in cursor sync but nothing blocking. Good enough for launch.

**S3 — Base Case (35%):** Ships at 7–8 weeks (slight overrun). Some conflicts in mobile Safari. Liveblocks pricing becomes a topic at month 3 when you hit 1,000 MAU. Manageable.

**S4 — Pessimistic (20%):** Team chose raw WebSockets to avoid lock-in. Spent 4 of 6 weeks on WebSocket infrastructure + conflict resolution. Feature ships half-built. Concurrent edit conflicts cause data loss bugs in production. Customer complaints.

**S5 — Worst Case (10%):** Team chose raw WebSockets + attempted CRDT. Hit the 6-week deadline with nothing shippable. Feature cut from roadmap. 6 weeks lost.

**Most likely path:** S3 — slight overrun, manageable costs, good outcome.
**Biggest risk:** S4/S5 if the team underestimates conflict resolution complexity and chooses raw WebSockets.

---

## Confidence Assessment

| Claim | Score | Basis |
|---|---|---|
| CRDT/OT is genuinely hard to build from scratch | 95% | Established engineering knowledge — Google, Figma, Notion all use specialized implementations |
| Liveblocks will integrate with Next.js in < 1 week | 85% | Well-documented, active community, Next.js is their primary target |
| Raw WebSockets are the wrong choice for 2 devs / 6 weeks | 80% | Constraint-based — with more time/team it would be viable |
| Liveblocks pricing stays reasonable at <10K MAU | 70% | Based on current pricing — could change |
| SSE is wrong for this use case | 90% | SSE is one-directional, can't send cursor positions from client |

**Overall confidence: 82%**
**I'm most certain about:** SSE being wrong (it's one-way) and CRDT complexity.
**I'm least certain about:** Long-term Liveblocks pricing and lock-in risk.
**Validate by:** Spike a Liveblocks proof-of-concept in 2 days before committing to the architecture.

---

## Plan & Execution

### Recommended Architecture

```
Next.js App
    │
    ├── Liveblocks (real-time sync layer)
    │     ├── Yjs CRDT for document conflict resolution
    │     ├── Presence API for live cursors + user awareness
    │     └── Storage API for persistent room state
    │
    └── Your existing PostgreSQL DB (source of truth for saved documents)

Sync pattern:
  - Active editing session → Liveblocks (real-time, ephemeral)
  - Document save → flush Yjs state → persist to PostgreSQL
  - Page load → fetch from PostgreSQL → initialize Yjs state
```

### Step-by-Step (6 weeks)

**Week 1 — Spike & Validate:**
1. Create a Liveblocks account, run their Next.js starter in 1 day
2. Confirm cursor sync and concurrent edits work locally
3. Validate pricing model against your expected MAU
4. Decision gate: if spike fails, reconsider architecture before investing further

**Week 2 — Core Integration:**
5. Install `@liveblocks/client` and `@liveblocks/react` in your Next.js app
6. Wrap document editor component in `RoomProvider`
7. Implement presence (live cursors showing other users)

**Week 3 — Conflict Resolution:**
8. Integrate Yjs via `@liveblocks/yjs`
9. Connect your text editor (TipTap or Slate) to Yjs document
10. Test concurrent editing between 2 browser tabs

**Week 4 — Persistence Layer:**
11. Implement save-to-database flow (flush Yjs → PostgreSQL)
12. Implement load-from-database flow (PostgreSQL → initialize Yjs)
13. Handle edge cases: what happens when a user is offline?

**Week 5 — Polish & Edge Cases:**
14. Implement user avatars in presence (show who's editing)
15. Handle disconnect/reconnect gracefully
16. Test on mobile Safari (historically problematic for WebSocket apps)

**Week 6 — Harden & Ship:**
17. Load test with 20 concurrent users in a single room
18. Set up Liveblocks webhook for billing/usage monitoring
19. Write runbook for incident response if Liveblocks has an outage
20. Ship to 10% of users as beta, monitor for issues

### Early Warning Triggers

| Signal | Action |
|---|---|
| Spike takes > 3 days | Re-evaluate architecture before week 2 begins |
| Liveblocks pricing > $500/mo before 5K MAU | Evaluate Partykit (open source alternative) |
| Data loss bug in concurrent edits | Stop, roll back feature, fix CRDT sync before re-enabling |
| Mobile Safari WebSocket failures > 5% | Add SSE fallback polling as backup transport |

### Definition of Done

- [ ] Two users can edit the same document simultaneously without data loss
- [ ] Live cursors show other users' positions in real time
- [ ] Document persists correctly after all users disconnect
- [ ] Works on Chrome, Firefox, Safari (desktop + mobile)
- [ ] Tested with 10+ concurrent users in one room
- [ ] Incident runbook written for Liveblocks outage scenario

---

*Deep Confidence analysis complete. Overall confidence: 82%. Proceed with the Liveblocks spike in Week 1 to validate before full commitment.*
