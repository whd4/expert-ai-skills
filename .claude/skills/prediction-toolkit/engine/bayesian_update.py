"""Bayesian update.

Two forms covered:

1. **Simple probability update** — `probability_update(prior, likelihood...)`.
   Answers: "I thought P(H)=30%. I observed evidence E. What's P(H | E)?"
   Formula: P(H|E) = P(E|H)*P(H) / P(E)

2. **Beta-Binomial conjugate update** — `beta_binomial_update(alpha, beta, successes, trials)`.
   Answers: "I had a prior belief about a rate (CTR, conversion, hit rate, P(success)).
   I just ran a trial: k successes out of n. What does my posterior look like?"
   This is the workhorse for A/B testing and small-sample rate estimation.

Best for:
  - Updating a probability with new evidence
  - Small-sample rate estimation (A/B tests with few conversions)
  - Sequential decision-making where you accumulate evidence
  - Any setting where you have a prior + likelihood

Not for:
  - Point forecasting (use forecasting methods)
  - No prior available (use bootstrap or frequentist methods)
  - Huge samples where prior barely matters (any method works)
"""
from __future__ import annotations

import math
from typing import Any


def probability_update(
    prior: float,
    likelihood_given_h: float,
    likelihood_given_not_h: float,
) -> dict[str, Any]:
    """Bayes' rule for a single hypothesis.

    Args:
        prior: P(H) — prior probability the hypothesis is true, in (0, 1).
        likelihood_given_h: P(E | H) — probability of seeing the evidence IF H true.
        likelihood_given_not_h: P(E | not H) — probability of seeing the evidence IF H false.

    Returns:
        dict with prior, posterior, likelihood ratio, evidence marginal.

    Example (medical test):
        prior = 0.01  # 1% disease prevalence
        sensitivity = 0.99  # P(positive | disease)
        false_positive = 0.05  # P(positive | healthy)
        probability_update(0.01, 0.99, 0.05)
        # posterior ≈ 0.167 — even with a 99% sensitive test, only 17% chance you have it
    """
    if not 0.0 <= prior <= 1.0:
        raise ValueError(f"prior must be in [0, 1], got {prior}")
    if not 0.0 <= likelihood_given_h <= 1.0:
        raise ValueError(f"likelihood_given_h must be in [0, 1], got {likelihood_given_h}")
    if not 0.0 <= likelihood_given_not_h <= 1.0:
        raise ValueError(f"likelihood_given_not_h must be in [0, 1], got {likelihood_given_not_h}")

    evidence = likelihood_given_h * prior + likelihood_given_not_h * (1 - prior)
    if evidence == 0:
        raise ValueError("evidence probability is 0 — the observation is impossible under both hypotheses")

    posterior = (likelihood_given_h * prior) / evidence

    # Likelihood ratio (Bayes factor): ratio of how much the evidence favors H vs not-H
    if likelihood_given_not_h > 0:
        likelihood_ratio = likelihood_given_h / likelihood_given_not_h
    else:
        likelihood_ratio = float("inf")

    return {
        "method": "bayesian_probability_update",
        "prior": prior,
        "likelihood_given_h": likelihood_given_h,
        "likelihood_given_not_h": likelihood_given_not_h,
        "evidence_probability": round(evidence, 6),
        "posterior": round(posterior, 6),
        "likelihood_ratio": round(likelihood_ratio, 4) if likelihood_ratio != float("inf") else None,
        "interpretation": _interpret_update(prior, posterior, likelihood_ratio),
    }


def _interpret_update(prior: float, posterior: float, lr: float) -> str:
    delta = posterior - prior
    if abs(delta) < 0.05:
        return f"evidence barely moved belief ({prior:.1%} → {posterior:.1%})"
    direction = "up" if delta > 0 else "down"
    strength = "strongly" if abs(delta) > 0.3 else "moderately" if abs(delta) > 0.15 else "modestly"
    return f"belief moved {direction} {strength}: {prior:.1%} → {posterior:.1%} (LR={lr:.2f})"


def beta_binomial_update(
    alpha: float,
    beta: float,
    successes: int,
    trials: int,
) -> dict[str, Any]:
    """Update a Beta prior with Binomial evidence (conjugate update).

    The Beta distribution is the standard prior for probabilities/rates.
    Beta(alpha, beta) has mean = alpha / (alpha + beta).

    Common priors:
      - Beta(1, 1)  = uniform, "I know nothing"
      - Beta(2, 2)  = weakly centered on 0.5
      - Beta(2, 8)  = weak prior that rate is ~20%
      - Beta(5, 95) = strong prior that rate is ~5% (e.g., CTR on ads)

    After k successes out of n trials:
      posterior = Beta(alpha + k, beta + n - k)

    Args:
        alpha: Prior alpha (successes + 1 conceptually).
        beta: Prior beta (failures + 1 conceptually).
        successes: Observed successes.
        trials: Total trials (successes + failures).

    Returns:
        dict with prior_mean, posterior_mean, posterior alpha/beta,
        credible interval, and a comparison.

    Example (A/B test):
        # Started with weak prior that CTR is ~5% (Beta(5, 95))
        # Ran test, got 3 clicks out of 50 impressions
        beta_binomial_update(5, 95, successes=3, trials=50)
        # posterior mean ~= 8/150 = 5.3%, tighter distribution
    """
    if alpha <= 0 or beta <= 0:
        raise ValueError(f"alpha and beta must be positive, got alpha={alpha}, beta={beta}")
    if trials < 0 or successes < 0:
        raise ValueError("trials and successes must be non-negative")
    if successes > trials:
        raise ValueError(f"successes ({successes}) cannot exceed trials ({trials})")

    failures = trials - successes
    post_alpha = alpha + successes
    post_beta = beta + failures

    prior_mean = alpha / (alpha + beta)
    posterior_mean = post_alpha / (post_alpha + post_beta)

    # Credible interval (95% by default via Beta inverse CDF — compute
    # numerically with a simple method since scipy isn't guaranteed)
    ci_low, ci_high = _beta_ci(post_alpha, post_beta, ci=0.95)

    prior_variance = (alpha * beta) / ((alpha + beta) ** 2 * (alpha + beta + 1))
    posterior_variance = (post_alpha * post_beta) / ((post_alpha + post_beta) ** 2 * (post_alpha + post_beta + 1))
    prior_stddev = prior_variance ** 0.5
    posterior_stddev = posterior_variance ** 0.5

    return {
        "method": "beta_binomial_update",
        "prior": {
            "alpha": alpha,
            "beta": beta,
            "mean": round(prior_mean, 6),
            "stddev": round(prior_stddev, 6),
        },
        "evidence": {
            "successes": successes,
            "trials": trials,
            "rate": round(successes / trials, 6) if trials > 0 else None,
        },
        "posterior": {
            "alpha": post_alpha,
            "beta": post_beta,
            "mean": round(posterior_mean, 6),
            "stddev": round(posterior_stddev, 6),
            "ci_95_lower": round(ci_low, 6),
            "ci_95_upper": round(ci_high, 6),
        },
        "interpretation": _interpret_beta_update(prior_mean, posterior_mean, trials),
    }


def _interpret_beta_update(prior_mean: float, posterior_mean: float, trials: int) -> str:
    delta = posterior_mean - prior_mean
    if trials < 10:
        strength = "weakly"
    elif trials < 100:
        strength = "modestly"
    else:
        strength = "strongly"
    if abs(delta) < 0.01:
        return f"evidence ({trials} trials) did not meaningfully change belief ({prior_mean:.1%} → {posterior_mean:.1%})"
    direction = "up" if delta > 0 else "down"
    return f"posterior {strength} moved {direction}: {prior_mean:.1%} → {posterior_mean:.1%} after {trials} trials"


def _beta_ci(alpha: float, beta: float, ci: float = 0.95) -> tuple[float, float]:
    """Numerical Beta credible interval via bisection on the CDF.

    Uses the regularized incomplete beta function, computed via a continued
    fraction (Lentz's algorithm). Good enough for 4-digit precision on
    typical prior/posterior parameters.
    """
    tail = (1 - ci) / 2
    lo = _beta_inverse_cdf(alpha, beta, tail)
    hi = _beta_inverse_cdf(alpha, beta, 1 - tail)
    return lo, hi


def _beta_inverse_cdf(alpha: float, beta: float, p: float) -> float:
    """Find x such that CDF(x; alpha, beta) = p, by bisection."""
    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if _beta_cdf(mid, alpha, beta) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _beta_cdf(x: float, alpha: float, beta: float) -> float:
    """Regularized incomplete beta function I_x(alpha, beta) — Beta CDF."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    # Use the symmetry transformation for numerical stability
    if x > (alpha + 1) / (alpha + beta + 2):
        return 1 - _beta_cdf(1 - x, beta, alpha)

    lbeta = math.lgamma(alpha) + math.lgamma(beta) - math.lgamma(alpha + beta)
    front = math.exp(math.log(x) * alpha + math.log(1 - x) * beta - lbeta) / alpha
    return front * _betacf(x, alpha, beta)


def _betacf(x: float, a: float, b: float, max_iter: int = 200, eps: float = 1e-10) -> float:
    """Continued fraction for the incomplete beta function (Lentz's method)."""
    qab = a + b
    qap = a + 1
    qam = a - 1
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < 1e-30:
        d = 1e-30
    d = 1.0 / d
    h = d
    for m in range(1, max_iter + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1.0 + aa / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1.0 + aa / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def render_probability_update(result: dict) -> str:
    lines = []
    lines.append("=" * 60)
    lines.append("  BAYESIAN PROBABILITY UPDATE")
    lines.append("=" * 60)
    lines.append(f"  Prior P(H):           {result['prior']:.4f}")
    lines.append(f"  P(E | H):             {result['likelihood_given_h']:.4f}")
    lines.append(f"  P(E | not H):         {result['likelihood_given_not_h']:.4f}")
    lines.append(f"  Evidence P(E):        {result['evidence_probability']:.4f}")
    lines.append(f"  Likelihood ratio:     {result['likelihood_ratio']}")
    lines.append("  " + "-" * 50)
    lines.append(f"  Posterior P(H | E):   {result['posterior']:.4f}")
    lines.append("")
    lines.append(f"  {result['interpretation']}")
    lines.append("=" * 60)
    return "\n".join(lines) + "\n"


def render_beta_update(result: dict) -> str:
    lines = []
    lines.append("=" * 60)
    lines.append("  BETA-BINOMIAL UPDATE")
    lines.append("=" * 60)
    prior = result["prior"]
    evidence = result["evidence"]
    post = result["posterior"]
    lines.append(f"  Prior:      Beta({prior['alpha']}, {prior['beta']})")
    lines.append(f"              mean={prior['mean']:.4f}  stddev={prior['stddev']:.4f}")
    lines.append(f"  Evidence:   {evidence['successes']} / {evidence['trials']} "
                 f"(rate={evidence['rate']:.4f})" if evidence["rate"] is not None else "  Evidence:   none")
    lines.append("  " + "-" * 50)
    lines.append(f"  Posterior:  Beta({post['alpha']:.1f}, {post['beta']:.1f})")
    lines.append(f"              mean={post['mean']:.4f}  stddev={post['stddev']:.4f}")
    lines.append(f"              95% CI: [{post['ci_95_lower']:.4f}, {post['ci_95_upper']:.4f}]")
    lines.append("")
    lines.append(f"  {result['interpretation']}")
    lines.append("=" * 60)
    return "\n".join(lines) + "\n"
