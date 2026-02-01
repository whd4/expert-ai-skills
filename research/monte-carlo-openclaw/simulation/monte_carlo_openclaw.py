#!/usr/bin/env python3
"""
Monte Carlo Prediction Model for OpenClaw (formerly ClawdBot/Moltbot)
=====================================================================
Simulates 5 future scenarios across 30-day, 60-day, and 12-month horizons.

Methodology:
- 10,000 simulation runs per scenario
- Key variables: GitHub stars, active users, revenue, security incidents, ecosystem growth
- Confidence intervals: 80% and 95%
- Data anchored to real observed metrics as of Jan 31, 2026

Author: AI Research Agent (Claude Opus 4.5)
Date: February 1, 2026
"""

import random
import math
import json
import os
from dataclasses import dataclass, field, asdict
from typing import List, Dict

# ── Seed for reproducibility ──
random.seed(42)

# ═══════════════════════════════════════════════════════════════
# OBSERVED DATA (anchored to real-world metrics, Jan 31 2026)
# ═══════════════════════════════════════════════════════════════

BASELINE = {
    "github_stars": 133_000,          # As of Jan 31, 2026
    "weekly_star_rate": 30_000,       # Peak week
    "active_deployments": 180_000,    # VentureBeat estimate
    "monthly_api_spend_avg_usd": 50,  # Median user ~$30-70/mo
    "hosted_platform_launched": True, # Jan 31, 2026
    "security_incidents_known": 3,    # Cisco flagged critical issues
    "ecosystem_projects": 5,          # Moltbook, Molthub, DeepSeek fork, etc.
    "contributors": 400,              # Estimated from repo activity
    "project_age_days": 65,           # Nov 2025 → Jan 31 2026
}

N_SIMULATIONS = 10_000
HORIZONS = {"30_days": 30, "60_days": 60, "12_months": 365}


# ═══════════════════════════════════════════════════════════════
# SCENARIO DEFINITIONS
# ═══════════════════════════════════════════════════════════════

@dataclass
class ScenarioParams:
    name: str
    description: str
    # Growth modifiers (multipliers on baseline rates)
    star_growth_mu: float       # Mean daily star growth multiplier
    star_growth_sigma: float    # Volatility
    user_growth_mu: float       # Mean daily active-user growth rate
    user_growth_sigma: float
    revenue_per_user_mu: float  # Monthly revenue per hosted user
    revenue_per_user_sigma: float
    hosted_adoption_rate: float # Fraction of users moving to hosted
    security_incident_lambda: float  # Poisson rate per 30 days
    ecosystem_growth_rate: float     # New projects per month
    churn_rate_monthly: float        # User churn per month
    sentiment: str                   # bull / bear / neutral


SCENARIOS = [
    # ── Scenario 1: HYPERGROWTH (Best Case) ──
    ScenarioParams(
        name="S1: Hypergrowth Dominance",
        description="OpenClaw becomes the default personal AI layer. Major tech companies integrate it. Security issues resolved rapidly. Hosted platform achieves product-market fit.",
        star_growth_mu=1500, star_growth_sigma=600,
        user_growth_mu=0.035, user_growth_sigma=0.012,
        revenue_per_user_mu=25, revenue_per_user_sigma=8,
        hosted_adoption_rate=0.30,
        security_incident_lambda=0.3,
        ecosystem_growth_rate=12,
        churn_rate_monthly=0.05,
        sentiment="bull",
    ),
    # ── Scenario 2: STRONG GROWTH (Optimistic) ──
    ScenarioParams(
        name="S2: Strong Organic Growth",
        description="Sustained community growth. Hosted platform gains traction. Security posture improves but remains a concern. Enterprise pilots begin.",
        star_growth_mu=800, star_growth_sigma=400,
        user_growth_mu=0.022, user_growth_sigma=0.008,
        revenue_per_user_mu=18, revenue_per_user_sigma=6,
        hosted_adoption_rate=0.18,
        security_incident_lambda=0.8,
        ecosystem_growth_rate=7,
        churn_rate_monthly=0.08,
        sentiment="bull",
    ),
    # ── Scenario 3: BASELINE PLATEAU (Neutral) ──
    ScenarioParams(
        name="S3: Plateau & Stabilization",
        description="Initial hype fades. Growth decelerates to normal open-source rates. Hosted platform has modest adoption. Security concerns persist but don't cause a crisis.",
        star_growth_mu=200, star_growth_sigma=150,
        user_growth_mu=0.008, user_growth_sigma=0.005,
        revenue_per_user_mu=12, revenue_per_user_sigma=5,
        hosted_adoption_rate=0.10,
        security_incident_lambda=1.5,
        ecosystem_growth_rate=3,
        churn_rate_monthly=0.12,
        sentiment="neutral",
    ),
    # ── Scenario 4: SECURITY CRISIS (Pessimistic) ──
    ScenarioParams(
        name="S4: Security Crisis & Erosion",
        description="Major security breach occurs. Enterprise and government users flee. Negative press cycle. Community fractures. Hosted platform fails to differentiate.",
        star_growth_mu=50, star_growth_sigma=100,
        user_growth_mu=-0.005, user_growth_sigma=0.010,
        revenue_per_user_mu=8, revenue_per_user_sigma=4,
        hosted_adoption_rate=0.05,
        security_incident_lambda=4.0,
        ecosystem_growth_rate=1,
        churn_rate_monthly=0.25,
        sentiment="bear",
    ),
    # ── Scenario 5: COLLAPSE (Worst Case) ──
    ScenarioParams(
        name="S5: Project Collapse",
        description="Regulatory crackdown. Anthropic or major AI provider blocks API access. Creator burns out. Community forks splinter the ecosystem. Mass exodus.",
        star_growth_mu=-50, star_growth_sigma=200,
        user_growth_mu=-0.02, user_growth_sigma=0.015,
        revenue_per_user_mu=5, revenue_per_user_sigma=3,
        hosted_adoption_rate=0.02,
        security_incident_lambda=6.0,
        ecosystem_growth_rate=-1,
        churn_rate_monthly=0.40,
        sentiment="bear",
    ),
]


# ═══════════════════════════════════════════════════════════════
# MONTE CARLO ENGINE
# ═══════════════════════════════════════════════════════════════

def poisson(lam: float) -> int:
    """Simple Poisson random variate via inverse transform."""
    L = math.exp(-lam)
    k = 0
    p = 1.0
    while True:
        k += 1
        p *= random.random()
        if p < L:
            return k - 1


def gauss_positive(mu, sigma):
    return max(0, random.gauss(mu, sigma))


def simulate_scenario(params: ScenarioParams, days: int) -> Dict:
    """Run one Monte Carlo path for a scenario over `days`."""
    stars = BASELINE["github_stars"]
    users = BASELINE["active_deployments"]
    hosted_users = 0
    total_revenue = 0.0
    security_incidents = BASELINE["security_incidents_known"]
    ecosystem = BASELINE["ecosystem_projects"]
    contributors = BASELINE["contributors"]

    for d in range(days):
        # Daily star growth with noise
        daily_stars = max(0, random.gauss(params.star_growth_mu, params.star_growth_sigma))
        stars += daily_stars

        # User growth (compound daily)
        daily_user_growth = random.gauss(params.user_growth_mu, params.user_growth_sigma)
        users = max(1000, users * (1 + daily_user_growth / 30))

        # Monthly churn applied daily
        if d % 30 == 29:
            churn = users * params.churn_rate_monthly * random.uniform(0.7, 1.3)
            users = max(1000, users - churn)

        # Hosted platform adoption
        hosted_users = users * params.hosted_adoption_rate * random.uniform(0.8, 1.2)

        # Revenue from hosted users (monthly, pro-rated daily)
        rev_per_user = gauss_positive(params.revenue_per_user_mu, params.revenue_per_user_sigma)
        total_revenue += (hosted_users * rev_per_user) / 30

        # Security incidents (Poisson per 30-day window)
        if d % 30 == 0:
            security_incidents += poisson(params.security_incident_lambda)

        # Ecosystem growth
        if d % 30 == 0 and d > 0:
            ecosystem += max(0, int(random.gauss(params.ecosystem_growth_rate, 2)))

        # Contributor growth proportional to users
        if d % 7 == 0:
            contributors += max(0, int(users / 50000 * random.uniform(1, 5)))

    return {
        "github_stars": int(stars),
        "active_users": int(users),
        "hosted_users": int(hosted_users),
        "monthly_recurring_revenue_usd": round(hosted_users * params.revenue_per_user_mu, 2),
        "cumulative_revenue_usd": round(total_revenue, 2),
        "security_incidents_total": security_incidents,
        "ecosystem_projects": ecosystem,
        "contributors": contributors,
    }


def run_monte_carlo(params: ScenarioParams, days: int, n: int = N_SIMULATIONS) -> Dict:
    """Run n simulations and compute statistics."""
    results = [simulate_scenario(params, days) for _ in range(n)]

    stats = {}
    keys = results[0].keys()
    for k in keys:
        values = sorted([r[k] for r in results])
        n_vals = len(values)
        stats[k] = {
            "mean": round(sum(values) / n_vals, 2),
            "median": round(values[n_vals // 2], 2),
            "p5": round(values[int(n_vals * 0.05)], 2),
            "p10": round(values[int(n_vals * 0.10)], 2),
            "p25": round(values[int(n_vals * 0.25)], 2),
            "p75": round(values[int(n_vals * 0.75)], 2),
            "p90": round(values[int(n_vals * 0.90)], 2),
            "p95": round(values[int(n_vals * 0.95)], 2),
            "min": round(values[0], 2),
            "max": round(values[-1], 2),
        }
    return stats


# ═══════════════════════════════════════════════════════════════
# MAIN EXECUTION
# ═══════════════════════════════════════════════════════════════

def main():
    all_results = {}

    for scenario in SCENARIOS:
        all_results[scenario.name] = {
            "description": scenario.description,
            "sentiment": scenario.sentiment,
            "horizons": {}
        }
        for horizon_name, days in HORIZONS.items():
            print(f"  Running {scenario.name} → {horizon_name} ({N_SIMULATIONS} sims)...")
            stats = run_monte_carlo(scenario, days)
            all_results[scenario.name]["horizons"][horizon_name] = stats

    # Write results
    out_path = os.path.join(os.path.dirname(__file__), "..", "data", "simulation_results.json")
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\n✓ Results written to {out_path}")

    # Print summary table
    print("\n" + "=" * 90)
    print("MONTE CARLO SIMULATION SUMMARY — OpenClaw Future Predictions")
    print("=" * 90)

    for scenario in SCENARIOS:
        sr = all_results[scenario.name]
        print(f"\n{'─' * 90}")
        print(f"  {scenario.name}  [{sr['sentiment'].upper()}]")
        print(f"  {scenario.description}")
        print(f"{'─' * 90}")
        print(f"  {'Metric':<30} {'30 Days (median)':<20} {'60 Days (median)':<20} {'12 Months (median)':<20}")
        print(f"  {'─'*28}   {'─'*18}   {'─'*18}   {'─'*18}")

        for metric in ["github_stars", "active_users", "hosted_users",
                        "monthly_recurring_revenue_usd", "security_incidents_total",
                        "ecosystem_projects"]:
            vals = []
            for h in ["30_days", "60_days", "12_months"]:
                v = sr["horizons"][h][metric]["median"]
                if v >= 1_000_000:
                    vals.append(f"{v/1_000_000:.1f}M")
                elif v >= 1_000:
                    vals.append(f"{v/1_000:.1f}K")
                else:
                    vals.append(f"{v:,.0f}")
            label = metric.replace("_", " ").title()
            print(f"  {label:<30} {vals[0]:<20} {vals[1]:<20} {vals[2]:<20}")

    print(f"\n{'=' * 90}")
    print(f"Based on {N_SIMULATIONS:,} Monte Carlo simulations per scenario per horizon.")
    print(f"Baseline data: 133K stars, 180K deployments as of Jan 31, 2026.")
    print(f"{'=' * 90}")


if __name__ == "__main__":
    main()
