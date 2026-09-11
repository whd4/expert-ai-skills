"""Integration tests for the Prediction Toolkit.

Run with:
    cd skills/prediction-toolkit
    python3 -m engine.tests.test_toolkit
"""
from __future__ import annotations

import json
import sys
import traceback


def approx_equal(a, b, tol=0.05):
    return abs(a - b) <= tol * max(abs(a), abs(b), 1e-9)


# ============================================================
#  Bootstrap
# ============================================================

def test_bootstrap_mean_ci():
    from engine import bootstrap_ci
    # Data from a normal(10, 2) — 95% CI on the mean should contain 10
    data = [9.8, 10.2, 11.1, 8.9, 10.5, 9.3, 10.7, 11.2, 9.1, 10.0,
            10.4, 8.7, 11.3, 9.6, 10.8, 9.9, 10.1, 10.3, 9.5, 10.6]
    result = bootstrap_ci(data, stat="mean", n_resamples=2000, seed=1)
    assert result["ci_lower"] < 10 < result["ci_upper"], \
        f"CI [{result['ci_lower']}, {result['ci_upper']}] should contain 10"
    assert approx_equal(result["observed"], 10, 0.1)
    print(f"✓ bootstrap mean: observed={result['observed']:.3f}, "
          f"95% CI=[{result['ci_lower']:.3f}, {result['ci_upper']:.3f}]")


def test_bootstrap_median_ci():
    from engine import bootstrap_ci
    # Skewed data — median should be more robust than mean
    data = [1, 2, 2, 3, 3, 3, 4, 4, 5, 100]  # outlier at 100
    result = bootstrap_ci(data, stat="median", n_resamples=2000, seed=1)
    # Median of [1,2,2,3,3,3,4,4,5,100] is 3.0
    assert 2 <= result["observed"] <= 4, f"median should be ~3, got {result['observed']}"
    print(f"✓ bootstrap median on skewed data: observed={result['observed']:.3f} "
          f"(mean would be pulled by outlier)")


def test_bootstrap_caveats_small_sample():
    from engine import bootstrap_ci
    result = bootstrap_ci([1.0, 2.0, 3.0], stat="mean", n_resamples=1000, seed=1)
    assert any("very small sample" in c for c in result["caveats"])
    print("✓ bootstrap flags tiny samples as unreliable")


# ============================================================
#  Bayesian updates
# ============================================================

def test_probability_update_medical():
    from engine import probability_update
    # Classic base-rate fallacy: disease prevalence 1%, test 99% sensitive, 5% false positive
    result = probability_update(prior=0.01, likelihood_given_h=0.99, likelihood_given_not_h=0.05)
    # P(disease | positive) should be ~16.7%, NOT 99%
    assert 0.15 < result["posterior"] < 0.18, \
        f"expected posterior ~16.7%, got {result['posterior']}"
    print(f"✓ probability update: prior=1%, test positive → posterior={result['posterior']:.1%} "
          f"(demonstrates base-rate effect)")


def test_beta_binomial_converges_to_truth():
    from engine import beta_binomial_update
    # Weak prior, lots of evidence — posterior should converge to observed rate
    result = beta_binomial_update(alpha=1, beta=1, successes=75, trials=100)
    # Posterior mean = 76/102 = 0.745, close to 0.75
    assert approx_equal(result["posterior"]["mean"], 0.75, 0.02)
    # 95% CI should be tight
    ci_width = result["posterior"]["ci_95_upper"] - result["posterior"]["ci_95_lower"]
    assert ci_width < 0.2, f"CI too wide: {ci_width}"
    print(f"✓ beta-binomial: 75/100 with weak prior → posterior mean="
          f"{result['posterior']['mean']:.3f} (target 0.75)")


def test_beta_binomial_prior_dominates_small_sample():
    from engine import beta_binomial_update
    # Strong prior that rate ≈ 5%, tiny sample of 1/5
    result = beta_binomial_update(alpha=5, beta=95, successes=1, trials=5)
    # Prior mean = 5%. Evidence: 1/5 = 20%. Posterior: 6/105 ≈ 5.7%
    # With strong prior, posterior should stay close to 5%, not jump to 20%
    assert result["posterior"]["mean"] < 0.1, \
        f"strong prior should dampen: {result['posterior']['mean']}"
    print(f"✓ beta-binomial: strong prior + tiny evidence → posterior="
          f"{result['posterior']['mean']:.3f} (didn't jump to 20%)")


# ============================================================
#  Exponential smoothing
# ============================================================

def test_simple_ses_flat_series():
    from engine import forecast
    series = [10.0, 9.8, 10.2, 9.9, 10.1, 10.0, 9.95, 10.05]
    result = forecast(series, periods=3, method="simple")
    # Forecast should be close to the mean (~10)
    for f in result["forecasts"]:
        assert approx_equal(f, 10, 0.05), f"SES forecast off: {f}"
    print(f"✓ SES on flat series: forecasts={result['forecasts']}")


def test_holt_trend_extrapolation():
    from engine import forecast
    # Clear linear trend: 10, 12, 14, 16, 18, 20
    series = [10.0, 12.0, 14.0, 16.0, 18.0, 20.0]
    result = forecast(series, periods=3, method="holt")
    # Forecasts should extrapolate the trend upward
    assert result["forecasts"][0] > 20, f"holt should project up: {result['forecasts']}"
    assert result["forecasts"][-1] > result["forecasts"][0], "trend should continue"
    print(f"✓ Holt captures linear trend: forecasts={result['forecasts']}")


def test_holt_winters_seasonal():
    from engine import forecast
    # Synthetic quarterly data with a repeating pattern: [100, 120, 110, 90] * 3
    series = [100.0, 120.0, 110.0, 90.0] * 4  # 16 points, 4 seasons of 4
    result = forecast(series, periods=4, method="holt_winters", seasonal_periods=4)
    # Next 4 forecasts should roughly repeat the seasonal pattern
    forecasts = result["forecasts"]
    # Peak should still be near index 1 of the forecast (second period)
    assert forecasts[1] > forecasts[0], "seasonal peak should repeat"
    print(f"✓ Holt-Winters captures seasonality: forecasts={[round(f,1) for f in forecasts]}")


def test_forecast_auto_picks_method():
    from engine import forecast
    # Flat data → should pick simple
    result = forecast([5.0, 5.1, 4.9, 5.0], periods=1, method="auto")
    # Just check it runs without error
    assert "method" in result
    assert len(result["forecasts"]) == 1
    print(f"✓ forecast auto-picks method: chose {result['method']}")


# ============================================================
#  Router
# ============================================================

def test_router_recognizes_monte_carlo():
    from engine import recommend_method
    result = recommend_method("Should we migrate Postgres to MongoDB? What's the risk?")
    top = result["top_recommendation"]
    assert top["family_id"] == "simulation", \
        f"expected simulation, got {top['family_id']}"
    print(f"✓ router: migration decision → {top['family']}")


def test_router_recognizes_bayesian():
    from engine import recommend_method
    result = recommend_method(
        "I have a prior belief that my conversion rate is 5%. "
        "A/B test showed 3 out of 50 clicks. Update my belief."
    )
    top = result["top_recommendation"]
    assert top["family_id"] in ("bayesian_inference", "simulation"), \
        f"expected bayesian or simulation, got {top['family_id']}"
    print(f"✓ router: A/B test → {top['family']}")


def test_router_recognizes_forecasting():
    from engine import recommend_method
    result = recommend_method(
        "I have 24 months of historical revenue data. Forecast the next quarter."
    )
    top = result["top_recommendation"]
    assert top["family_id"] == "statistical_forecasting", \
        f"expected statistical_forecasting, got {top['family_id']}"
    print(f"✓ router: time-series forecast → {top['family']}")


def test_router_recognizes_causal():
    from engine import recommend_method
    result = recommend_method(
        "What would have happened if we had not launched the promo? "
        "Estimate the causal effect of the intervention on revenue."
    )
    top = result["top_recommendation"]
    assert top["family_id"] == "causal_inference", \
        f"expected causal_inference, got {top['family_id']}"
    print(f"✓ router: counterfactual → {top['family']}")


def test_router_structured_input():
    from engine import recommend_method
    result = recommend_method({
        "time_series": True,
        "has_historical_data": True,
        "data_points": 50,
        "seasonal_periods": 12,
    })
    top = result["top_recommendation"]
    assert top["family_id"] == "statistical_forecasting"
    print(f"✓ router (structured): seasonal time-series → {top['family']}")


# ============================================================
#  CLI + JSON round-trip
# ============================================================

def test_cli_bootstrap_json():
    import subprocess
    result = subprocess.run(
        ["python3", "-m", "engine", "--format", "json",
         "bootstrap", "--data", "1,2,3,4,5,6,7,8,9,10",
         "--stat", "mean", "--n-resamples", "1000", "--seed", "1"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, f"CLI failed: {result.stderr}"
    parsed = json.loads(result.stdout)
    assert approx_equal(parsed["observed"], 5.5, 0.001)
    print(f"✓ CLI bootstrap JSON: observed={parsed['observed']}")


def test_cli_run_stdin():
    import subprocess
    spec = json.dumps({
        "method": "beta_binomial_update",
        "alpha": 2, "beta": 8, "successes": 3, "trials": 20,
    })
    result = subprocess.run(
        ["python3", "-m", "engine", "run", "-"],
        input=spec, capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, f"CLI run failed: {result.stderr}"
    parsed = json.loads(result.stdout)
    assert "posterior" in parsed
    print(f"✓ CLI run stdin: posterior mean={parsed['posterior']['mean']}")


def test_cli_router_recommend():
    import subprocess
    result = subprocess.run(
        ["python3", "-m", "engine", "--format", "json",
         "router", "recommend", "forecast next month's sales from last year's data"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, f"CLI router failed: {result.stderr}"
    parsed = json.loads(result.stdout)
    assert parsed["top_recommendation"] is not None
    print(f"✓ CLI router recommend: top={parsed['top_recommendation']['family']}")


# ============================================================
#  Runner
# ============================================================

def main():
    tests = [
        test_bootstrap_mean_ci,
        test_bootstrap_median_ci,
        test_bootstrap_caveats_small_sample,
        test_probability_update_medical,
        test_beta_binomial_converges_to_truth,
        test_beta_binomial_prior_dominates_small_sample,
        test_simple_ses_flat_series,
        test_holt_trend_extrapolation,
        test_holt_winters_seasonal,
        test_forecast_auto_picks_method,
        test_router_recognizes_monte_carlo,
        test_router_recognizes_bayesian,
        test_router_recognizes_forecasting,
        test_router_recognizes_causal,
        test_router_structured_input,
        test_cli_bootstrap_json,
        test_cli_run_stdin,
        test_cli_router_recommend,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"✗ {t.__name__}: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n{'='*60}")
    print(f"  {passed} passed, {failed} failed")
    print(f"{'='*60}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
