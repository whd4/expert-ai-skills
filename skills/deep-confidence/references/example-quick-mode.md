# Deep Confidence: Quick Mode Example

## User Request
"Should I use PostgreSQL or MongoDB for my new SaaS app?"

---

## Internal Processing (runs silently in Quick Mode)

**ATLAS:** Goal = pick the right database. Constraints = SaaS app (unknown schema flexibility needs, unknown query complexity). Assumption = user hasn't started yet, schema is still flexible.

**MAD:** Best answer = PostgreSQL for most SaaS. Attack = MongoDB wins if schema changes frequently and you need document flexibility. Verdict = PostgreSQL still wins because most SaaS apps have more relational structure than teams realize at the start.

**Monte Carlo (compressed):** PostgreSQL path → S3 base case leads to solid, query-able data. MongoDB path → S4 risk is schema chaos at scale.

**Confidence:** 80% — this is strong general guidance, but schema shape matters.

---

## Output (Quick Mode)

**Use PostgreSQL.**

For a SaaS app, PostgreSQL is the right default 80%+ of the time. Your data will have more relational structure than you think — users belong to organizations, organizations have subscriptions, subscriptions have line items. PostgreSQL handles that cleanly.

MongoDB makes sense if:
- Your core data is genuinely document-shaped with unpredictable nested structure
- You need to store arbitrary user-defined fields
- You're building something like a CMS or form builder where every record looks different

If you're unsure which you are, you're probably PostgreSQL.

**Confidence: 80%** — holds unless your schema is genuinely document-heavy.
**Watch for:** If you find yourself doing many `$lookup` joins in MongoDB after 3 months, migrate early — it gets harder later.
