# Quick Monte Carlo Prediction Template

Use this template for fast assessments when a full analysis isn't needed.

---

## Quick Monte Carlo: [PROJECT NAME]

**Date:** [Date]

**Health:** [X/10] — [One-line summary of project state]

**Top 3 Risks:**
1. [Risk description] → [X]% probability → [Mitigation action]
2. [Risk description] → [X]% probability → [Mitigation action]
3. [Risk description] → [X]% probability → [Mitigation action]

**30-Day Outlook:**
- Best Case (S1): [Brief outcome]
- Base Case (S3): [Brief outcome]
- Worst Case (S5): [Brief outcome]

**#1 Action:** [Single most impactful thing to do right now]

---

## Example (Filled In)

## Quick Monte Carlo: E-Commerce Checkout Refactor

**Date:** February 2026

**Health:** 6/10 — Functional but fragile; 3 payment edge cases cause 15% of support tickets

**Top 3 Risks:**
1. Cart state desync during Stripe webhook race → 25% → Add idempotency keys + retry queue
2. Mobile Safari payment sheet failing → 20% → Test matrix + fallback flow
3. Inventory oversell on flash sales → 30% → Implement Redis-based locking

**30-Day Outlook:**
- Best Case (S1): Refactor complete, support tickets drop 60%, no payment failures
- Base Case (S3): Refactor 80% done, main bugs fixed, edge cases remain
- Worst Case (S5): Refactor stalls, Black Friday traffic causes payment failures, revenue loss

**#1 Action:** Implement idempotency keys on all Stripe webhook handlers this week

---

## When to Use Quick vs. Full

| Situation | Use Quick | Use Full |
|---|---|---|
| Daily standup check-in | ✅ | |
| Sprint planning | ✅ | |
| Major architecture decision | | ✅ |
| Quarterly roadmap planning | | ✅ |
| "Is this PR safe to merge?" | ✅ | |
| "Should we rewrite this system?" | | ✅ |
| Investor/stakeholder update | | ✅ |
| Pre-launch go/no-go | | ✅ |
