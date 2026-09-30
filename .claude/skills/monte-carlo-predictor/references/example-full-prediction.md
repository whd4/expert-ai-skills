# Example: Full Monte Carlo Prediction

## Project: "TaskFlow" — A Next.js SaaS Task Management App

This is a complete worked example showing how to apply the Monte Carlo Predictor skill to a real project.

---

# Monte Carlo Prediction: TaskFlow

## Date: February 2026

---

## 1. Current State Assessment

### Project Health Score: 5.5/10

| Indicator | Score | Finding |
|---|---|---|
| Code Quality | 6/10 | 340 files, moderate complexity. ESLint configured but 47 warnings suppressed. |
| Architecture Fit | 5/10 | Next.js App Router used, but 60% of routes still use Pages Router patterns. Migration incomplete. |
| Dependency Risk | 4/10 | 12 packages outdated by 6+ months. `next-auth` v4 still used (v5 stable for 8 months). |
| Velocity Signals | 7/10 | 3 contributors, 8 commits/week avg. Good cadence but single-person bottleneck on reviews. |
| Tech Debt Load | 4/10 | 87 TODOs, 12 FIXMEs, 3 HACK comments. Multiple `// @ts-ignore` suppressions. |
| Security Surface | 5/10 | JWT tokens stored in localStorage (should be httpOnly cookies). No rate limiting on auth endpoints. |
| Documentation Gap | 6/10 | README describes features that don't exist yet. API docs 3 months stale. |

### Decision Variables Identified

1. **App Router migration** — Complete the Pages→App Router migration or stay hybrid?
2. **Authentication upgrade** — Upgrade next-auth v4→v5 or switch to Clerk/Auth0?
3. **Database scaling** — Stay on SQLite/Prisma or move to PostgreSQL before launch?
4. **Real-time features** — Add WebSocket support for live collaboration or defer?
5. **Team size** — Stay at 3 developers or hire 2 more before launch?
6. **Launch timeline** — Ship MVP in 6 weeks or extend to 12 weeks for completeness?

### Divergence Report

| Intended | Actual | Divergence | Severity |
|---|---|---|---|
| "Full App Router migration" | 60% migrated, stalled for 2 months | ARCHITECTURE DRIFT | HIGH |
| "Type-safe codebase" | 23 `@ts-ignore`, 14 `any` types | QUALITY EROSION | MEDIUM |
| "Launch Q1 2026" | Core features 70% complete, Q1 ends in 4 weeks | TIMELINE RISK | HIGH |
| "Mobile-responsive" | 8 of 22 pages untested on mobile | COVERAGE GAP | MEDIUM |
| "Secure auth" | JWT in localStorage, no rate limiting | SECURITY GAP | CRITICAL |

---

## 2. Scenario Analysis

### S1: Best Case (10% probability)

Team completes App Router migration, upgrades auth, ships MVP on time. Early users love the product. Word of mouth drives organic growth.

| Metric | 30 Days | 90 Days | 12 Months |
|---|---|---|---|
| Feature Completion | 95% of MVP | 100% + 3 post-launch features | Full platform |
| Technical Debt | 3/10 (cleaned up) | 2/10 | 3/10 (controlled) |
| Bug Rate | 2/week | 1/week | 0.5/week |
| Active Users | 50 beta | 500 | 5,000 |
| Team Health | High energy | Sustainable pace | Growing team (6) |
| Security Posture | Hardened | Audited | SOC2 in progress |
| MRR | $0 | $2,500 | $35,000 |

### S2: Optimistic (25% probability)

MVP ships 2 weeks late but solid. Auth upgraded. Database migrated. Moderate early traction.

| Metric | 30 Days | 90 Days | 12 Months |
|---|---|---|---|
| Feature Completion | 80% of MVP | 100% MVP | MVP + 5 features |
| Technical Debt | 5/10 | 4/10 | 4/10 |
| Bug Rate | 4/week | 2/week | 1/week |
| Active Users | 20 beta | 200 | 1,500 |
| Team Health | Stretched but ok | Recovering | Stable at 4 devs |
| Security Posture | JWT fixed | Rate limiting added | Reasonable |
| MRR | $0 | $800 | $12,000 |

### S3: Base Case (35% probability)

MVP ships 4-6 weeks late. App Router migration stays incomplete. Auth partially upgraded. Product works but rough edges drive some churn.

| Metric | 30 Days | 90 Days | 12 Months |
|---|---|---|---|
| Feature Completion | 70% of MVP | 90% MVP | MVP + 2 features |
| Technical Debt | 6/10 | 6/10 (stable) | 7/10 (growing) |
| Bug Rate | 6/week | 4/week | 3/week |
| Active Users | 10 beta | 80 | 400 |
| Team Health | Tired, deadline stress | Moderate | 1 dev may leave |
| Security Posture | JWT partially fixed | Some gaps remain | Adequate |
| MRR | $0 | $200 | $3,000 |

### S4: Pessimistic (20% probability)

Launch delayed 3+ months. Key developer leaves. Tech debt compounds. Security incident damages reputation. Product enters crowded market too late.

| Metric | 30 Days | 90 Days | 12 Months |
|---|---|---|---|
| Feature Completion | 60% of MVP | 75% MVP | 90% MVP (still) |
| Technical Debt | 7/10 | 8/10 | 9/10 |
| Bug Rate | 8/week | 6/week | 5/week |
| Active Users | 5 beta | 30 | 80 |
| Team Health | Burnout starting | 1 dev left | 2 devs remaining |
| Security Posture | Unchanged | Incident occurs | Patched but damaged trust |
| MRR | $0 | $0 | $400 |

### S5: Worst Case (10% probability)

Security breach via localStorage JWT exploit. Launch cancelled. Team disbands. Project abandoned or requires complete rewrite.

| Metric | 30 Days | 90 Days | 12 Months |
|---|---|---|---|
| Feature Completion | 55% of MVP | 60% MVP | Project paused |
| Technical Debt | 8/10 | 9/10 | N/A |
| Bug Rate | 10/week | N/A | N/A |
| Active Users | 0 | 0 | 0 |
| Team Health | Crisis mode | Dissolved | N/A |
| Security Posture | Breached | N/A | N/A |
| MRR | $0 | $0 | $0 |

---

## 3. Cross-Scenario Comparison

| Metric (12 months) | S1 Best | S2 Optimistic | S3 Base | S4 Pessimistic | S5 Worst |
|---|---|---|---|---|---|
| Active Users | 5,000 | 1,500 | 400 | 80 | 0 |
| MRR | $35K | $12K | $3K | $400 | $0 |
| Tech Debt | 3/10 | 4/10 | 7/10 | 9/10 | N/A |
| Team Size | 6 | 4 | 2-3 | 2 | 0 |
| Product State | Platform | Solid MVP+ | Rough MVP | Incomplete | Dead |

**Probability-weighted expected MRR at 12 months:**
(0.10 × $35K) + (0.25 × $12K) + (0.35 × $3K) + (0.20 × $400) + (0.10 × $0) = **$7,630/mo**

---

## 4. Optimal Path Recommendation

### Best Decision Combination

```
DECISION MATRIX — Best Combination for Optimal Outcome
═══════════════════════════════════════════════════════════════════════════
Variable              Best Choice              Why
───────────────────────────────────────────────────────────────────────────
App Router migration  Complete it (2 weeks)     Unfinished migrations rot. Do it now or revert.
Authentication        Upgrade next-auth to v5   Smaller lift than switching providers. Fixes JWT issue.
Database              PostgreSQL NOW             SQLite will break at ~100 concurrent users. Migrate before launch.
Real-time features    DEFER                      Not MVP. Adds 4+ weeks. Ship without it.
Team size             Add 1 senior dev           Removes review bottleneck. 2 hires is overhead right now.
Launch timeline       Extend to 10 weeks         6 weeks is unrealistic given debt. 12 weeks loses urgency.
═══════════════════════════════════════════════════════════════════════════
Expected Outcome: S2 (Optimistic) with ~60% confidence
```

### Early Warning Triggers

| Signal | Threshold | Action |
|---|---|---|
| App Router migration stalls | No progress in 5 days | Pair-program or revert to Pages Router entirely |
| Auth upgrade blocked | Not merged in 10 days | Switch to Clerk (managed auth, removes problem) |
| Test coverage drops | Below 50% | Feature freeze until coverage restored |
| Sprint velocity declines | 2 consecutive sprints | Retrospective, reduce scope |
| Security vulnerability found | Any CVE in deps | Patch within 48 hours, no exceptions |
| Beta user churn | >50% in first week | User interviews, emergency UX fixes |

### Contingency Plans

```
IF auth migration fails      → THEN switch to Clerk managed auth (3 days) + remove all custom auth code
IF key developer leaves      → THEN reduce MVP scope by 30%, focus on core 3 features only
IF security breach occurs    → THEN immediate disclosure + 48-hour patch + hire security consultant
IF launch delayed past 12wk  → THEN ship what you have as "early access", iterate publicly
IF PostgreSQL migration slow → THEN use Neon serverless Postgres (managed, no ops overhead)
```

---

## 5. Confidence Assessment

### High Confidence (>80%)
- The localStorage JWT issue will cause a security incident if not fixed before public launch
- SQLite will become a bottleneck before reaching 200 active users
- The incomplete App Router migration is slowing down every new feature

### Medium Confidence (50-80%)
- Extending to 10 weeks will be enough time for a solid MVP
- Adding 1 developer will improve velocity (could slow it during onboarding)
- PostgreSQL migration will take 3-5 days with Prisma

### Low Confidence (<50%)
- User growth projections (no market validation data yet)
- Revenue estimates (pricing not tested with real users)
- Whether real-time features will be needed at all (could be over-engineering)

---

## 6. Next Actions

1. **TODAY: Fix localStorage JWT** — Move to httpOnly cookies. This is a CRITICAL security gap. (~4 hours)
2. **THIS WEEK: Complete App Router migration** — Assign 1 developer full-time for 5 days.
3. **THIS WEEK: Migrate to PostgreSQL** — Use Neon.tech for managed hosting. Update Prisma schema. (~2 days)
4. **NEXT WEEK: Upgrade next-auth v4→v5** — Follow official migration guide. (~3 days)
5. **NEXT WEEK: Add rate limiting** — `express-rate-limit` or Vercel edge middleware. (~1 day)

---

*This prediction should be re-run in 30 days with updated project data.*
