"""Integration tests for the Monte Carlo engine.

Run with:
    cd skills/monte-carlo-predictor
    python3 -m engine.tests.test_engine
"""
from __future__ import annotations

import json
import sys
import traceback


def approx_equal(a, b, tol=0.1):
    return abs(a - b) <= tol * max(abs(a), abs(b), 1e-9)


def test_uniform_stats():
    from engine import simulate
    report = simulate({
        "trials": 20000, "seed": 1,
        "variables": {"x": {"distribution": "uniform", "low": 0, "high": 100}},
        "outcomes": {"y": "x"},
    })
    mean = report["outcomes"]["y"]["stats"]["mean"]
    assert approx_equal(mean, 50, 0.02), f"uniform mean off: {mean}"
    print(f"✓ uniform: mean={mean:.2f} (expected 50)")


def test_normal_stats():
    from engine import simulate
    report = simulate({
        "trials": 20000, "seed": 1,
        "variables": {"x": {"distribution": "normal", "mean": 10, "stddev": 2}},
        "outcomes": {"y": "x"},
    })
    stats = report["outcomes"]["y"]["stats"]
    assert approx_equal(stats["mean"], 10, 0.02), f"normal mean off: {stats['mean']}"
    assert approx_equal(stats["stddev"], 2, 0.03), f"normal stddev off: {stats['stddev']}"
    print(f"✓ normal: mean={stats['mean']:.2f} stddev={stats['stddev']:.2f} (expected 10, 2)")


def test_triangular_stats():
    from engine import simulate
    report = simulate({
        "trials": 30000, "seed": 1,
        "variables": {"x": {"distribution": "triangular", "low": 0, "likely": 10, "high": 20}},
        "outcomes": {"y": "x"},
    })
    # Symmetric triangular mean = (low + likely + high) / 3 = 10
    mean = report["outcomes"]["y"]["stats"]["mean"]
    assert approx_equal(mean, 10, 0.02), f"triangular mean off: {mean}"
    print(f"✓ triangular: mean={mean:.2f} (expected 10)")


def test_beta_stats():
    from engine import simulate
    report = simulate({
        "trials": 30000, "seed": 1,
        "variables": {"x": {"distribution": "beta", "alpha": 2, "beta": 8}},
        "outcomes": {"y": "x"},
    })
    # Beta(2, 8) mean = 2/(2+8) = 0.2
    mean = report["outcomes"]["y"]["stats"]["mean"]
    assert approx_equal(mean, 0.2, 0.05), f"beta mean off: {mean}"
    print(f"✓ beta: mean={mean:.3f} (expected 0.200)")


def test_poisson_stats():
    from engine import simulate
    report = simulate({
        "trials": 30000, "seed": 1,
        "variables": {"x": {"distribution": "poisson", "lam": 5}},
        "outcomes": {"y": "x"},
    })
    # Poisson(5) mean = 5
    mean = report["outcomes"]["y"]["stats"]["mean"]
    assert approx_equal(mean, 5, 0.02), f"poisson mean off: {mean}"
    print(f"✓ poisson: mean={mean:.2f} (expected 5)")


def test_expression_arithmetic():
    from engine import simulate
    report = simulate({
        "trials": 5000, "seed": 1,
        "variables": {
            "a": {"distribution": "constant", "value": 3},
            "b": {"distribution": "constant", "value": 4},
        },
        "outcomes": {"sum": "a + b", "prod": "a * b", "hypot": "sqrt(a**2 + b**2)"},
    })
    assert report["outcomes"]["sum"]["stats"]["mean"] == 7
    assert report["outcomes"]["prod"]["stats"]["mean"] == 12
    assert approx_equal(report["outcomes"]["hypot"]["stats"]["mean"], 5, 0.001)
    print("✓ expressions: arithmetic + sqrt work")


def test_safe_eval_blocks_bad_code():
    from engine.expressions import safe_eval
    for bad in ["__import__('os')", "().__class__.__bases__", "print('hi')", "open('/etc/passwd')"]:
        try:
            safe_eval(bad, {})
        except ValueError:
            pass
        else:
            assert False, f"unsafe expression allowed: {bad}"
    print("✓ safe-eval: rejects attribute access, imports, and unknown calls")


def test_boolean_outcome_probability():
    from engine import simulate
    report = simulate({
        "trials": 20000, "seed": 1,
        "variables": {"x": {"distribution": "uniform", "low": 0, "high": 1}},
        "outcomes": {"hit": "x > 0.7"},
    })
    p = report["outcomes"]["hit"]["probability_true"]
    assert approx_equal(p, 0.3, 0.05), f"boolean prob off: {p}"
    print(f"✓ boolean outcome: P(hit) = {p:.3f} (expected ~0.300)")


def test_tornado_detects_driver():
    from engine import simulate
    report = simulate({
        "trials": 15000, "seed": 1,
        "variables": {
            "driver": {"distribution": "normal", "mean": 0, "stddev": 10},
            "noise":  {"distribution": "normal", "mean": 0, "stddev": 0.1},
        },
        "outcomes": {"y": "driver + noise"},
    })
    tornado = report["outcomes"]["y"]["tornado"]
    assert tornado[0]["variable"] == "driver", f"expected driver #1, got {tornado}"
    assert tornado[0]["correlation"] > 0.9
    print(f"✓ tornado: identified driver (r={tornado[0]['correlation']:.3f})")


def test_decision_optimizer_compare():
    from engine.decision_optimizer import compare
    options = {
        "low_risk": {
            "trials": 5000, "seed": 1,
            "variables": {"x": {"distribution": "normal", "mean": 50, "stddev": 5}},
            "outcomes": {"value": "x"},
        },
        "high_risk": {
            "trials": 5000, "seed": 1,
            "variables": {"x": {"distribution": "normal", "mean": 55, "stddev": 30}},
            "outcomes": {"value": "x"},
        },
    }
    result = compare(options, objective="outcomes.value.stats.mean")
    assert result["winner"] == "high_risk"
    # But P5 favors low_risk
    result_p5 = compare(options, objective="outcomes.value.stats.p5")
    assert result_p5["winner"] == "low_risk"
    print(f"✓ optimizer: mean picks high-risk, P5 picks low-risk")


def test_divergence_scanner_on_self():
    from engine.divergence_scanner import scan
    import os
    # Scan the parent skill directory
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    result = scan(here)
    assert "divergences" in result
    assert "summary" in result
    print(f"✓ scanner: found {result['summary']['total']} divergences on self-scan")


def test_cli_json_output():
    import subprocess
    spec = json.dumps({
        "trials": 2000, "seed": 1,
        "variables": {"x": {"distribution": "uniform", "low": 0, "high": 1}},
        "outcomes": {"y": "x * 2"},
    })
    result = subprocess.run(
        ["python3", "-m", "engine", "run", "-", "--format", "json"],
        input=spec, capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, f"CLI failed: {result.stderr}"
    report = json.loads(result.stdout)
    assert approx_equal(report["outcomes"]["y"]["stats"]["mean"], 1.0, 0.05)
    print(f"✓ CLI: JSON stdin→stdout works, mean={report['outcomes']['y']['stats']['mean']:.3f}")


def test_yaml_spec_loads():
    import subprocess, os
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    spec_path = os.path.join(here, "..", "templates", "spec-template.yaml")
    result = subprocess.run(
        ["python3", "-m", "engine", "run", spec_path, "--format", "json", "--no-histograms"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, f"YAML load failed: {result.stderr}"
    report = json.loads(result.stdout)
    assert report["trials"] == 10000
    assert "profitable" in report["outcomes"]
    print("✓ YAML: template spec runs end-to-end")


def main():
    tests = [
        test_uniform_stats,
        test_normal_stats,
        test_triangular_stats,
        test_beta_stats,
        test_poisson_stats,
        test_expression_arithmetic,
        test_safe_eval_blocks_bad_code,
        test_boolean_outcome_probability,
        test_tornado_detects_driver,
        test_decision_optimizer_compare,
        test_divergence_scanner_on_self,
        test_cli_json_output,
        test_yaml_spec_loads,
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
