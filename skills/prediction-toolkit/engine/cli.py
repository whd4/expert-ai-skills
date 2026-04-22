"""Unified CLI for the prediction toolkit.

Usage:
    python -m engine router recommend "forecast next quarter's revenue"
    python -m engine bootstrap --data 1,2,3,4,5 --stat mean --ci 0.95
    python -m engine bayes probability --prior 0.01 --p-e-given-h 0.99 --p-e-given-not-h 0.05
    python -m engine bayes beta --alpha 2 --beta 8 --successes 3 --trials 50
    python -m engine forecast --series 100,110,105,120,130 --periods 3
    python -m engine run -   (reads JSON from stdin, selects method by "method" key)
"""
from __future__ import annotations

import argparse
import json
import sys

from . import (
    bootstrap_ci,
    beta_binomial_update,
    probability_update,
    forecast,
    recommend_method,
)
from .bootstrap import render as render_bootstrap
from .bayesian_update import render_probability_update, render_beta_update
from .exponential_smoothing import render as render_forecast
from .router import render as render_router


def _parse_number_list(s: str) -> list[float]:
    return [float(x.strip()) for x in s.split(",") if x.strip()]


def cmd_router(args):
    if args.router_cmd == "recommend":
        result = recommend_method(args.problem)
        if args.format == "json":
            print(json.dumps(result, indent=2))
        else:
            print(render_router(result))


def cmd_bootstrap(args):
    data = _parse_number_list(args.data)
    result = bootstrap_ci(
        data=data, stat=args.stat, n_resamples=args.n_resamples,
        ci=args.ci, seed=args.seed,
    )
    if args.format == "json":
        print(json.dumps(result, indent=2))
    else:
        print(render_bootstrap(result))


def cmd_bayes(args):
    if args.bayes_cmd == "probability":
        result = probability_update(args.prior, args.p_e_given_h, args.p_e_given_not_h)
        if args.format == "json":
            print(json.dumps(result, indent=2))
        else:
            print(render_probability_update(result))
    elif args.bayes_cmd == "beta":
        result = beta_binomial_update(args.alpha, args.beta, args.successes, args.trials)
        if args.format == "json":
            print(json.dumps(result, indent=2))
        else:
            print(render_beta_update(result))


def cmd_forecast(args):
    series = _parse_number_list(args.series)
    result = forecast(
        series=series, periods=args.periods, method=args.method,
        alpha=args.alpha, beta=args.beta, gamma=args.gamma,
        seasonal_periods=args.seasonal_periods,
    )
    if args.format == "json":
        print(json.dumps(result, indent=2))
    else:
        print(render_forecast(result))


def cmd_run(args):
    """JSON stdin/stdout: dispatch based on 'method' key in the input.

    Example:
        echo '{"method":"bootstrap","data":[1,2,3,4,5],"stat":"mean"}' | python -m engine run -
    """
    if args.spec == "-":
        raw = sys.stdin.read()
    else:
        with open(args.spec) as f:
            raw = f.read()
    spec = json.loads(raw)
    method = spec.get("method")
    if method == "bootstrap":
        result = bootstrap_ci(
            data=spec["data"], stat=spec.get("stat", "mean"),
            n_resamples=spec.get("n_resamples", 10000),
            ci=spec.get("ci", 0.95), seed=spec.get("seed"),
        )
    elif method == "probability_update":
        result = probability_update(
            spec["prior"], spec["likelihood_given_h"], spec["likelihood_given_not_h"],
        )
    elif method == "beta_binomial_update":
        result = beta_binomial_update(
            spec["alpha"], spec["beta"], spec["successes"], spec["trials"],
        )
    elif method == "forecast":
        result = forecast(
            series=spec["series"], periods=spec.get("periods", 1),
            method=spec.get("forecast_method", "auto"),
            alpha=spec.get("alpha"), beta=spec.get("beta"), gamma=spec.get("gamma"),
            seasonal_periods=spec.get("seasonal_periods"),
        )
    elif method == "recommend":
        result = recommend_method(spec.get("problem", ""))
    else:
        print(json.dumps({
            "error": f"unknown method {method!r}",
            "available": ["bootstrap", "probability_update", "beta_binomial_update", "forecast", "recommend"],
        }), file=sys.stderr)
        sys.exit(1)
    print(json.dumps(result, indent=2))


def main():
    ap = argparse.ArgumentParser(prog="engine", description="Prediction Toolkit CLI")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_router = sub.add_parser("router", help="Recommend a prediction method for a problem")
    rsub = p_router.add_subparsers(dest="router_cmd", required=True)
    p_rec = rsub.add_parser("recommend")
    p_rec.add_argument("problem", help="Free-text problem description")
    p_router.set_defaults(func=cmd_router)

    p_boot = sub.add_parser("bootstrap", help="Bootstrap confidence interval")
    p_boot.add_argument("--data", required=True, help="Comma-separated numbers")
    p_boot.add_argument("--stat", default="mean",
                        choices=["mean", "median", "stdev", "variance", "min", "max", "sum"])
    p_boot.add_argument("--n-resamples", type=int, default=10000)
    p_boot.add_argument("--ci", type=float, default=0.95)
    p_boot.add_argument("--seed", type=int, default=None)
    p_boot.set_defaults(func=cmd_bootstrap)

    p_bayes = sub.add_parser("bayes", help="Bayesian updates")
    bsub = p_bayes.add_subparsers(dest="bayes_cmd", required=True)
    p_prob = bsub.add_parser("probability", help="Simple P(H|E) update")
    p_prob.add_argument("--prior", type=float, required=True)
    p_prob.add_argument("--p-e-given-h", type=float, required=True, dest="p_e_given_h")
    p_prob.add_argument("--p-e-given-not-h", type=float, required=True, dest="p_e_given_not_h")
    p_beta = bsub.add_parser("beta", help="Beta-Binomial conjugate update")
    p_beta.add_argument("--alpha", type=float, required=True)
    p_beta.add_argument("--beta", type=float, required=True)
    p_beta.add_argument("--successes", type=int, required=True)
    p_beta.add_argument("--trials", type=int, required=True)
    p_bayes.set_defaults(func=cmd_bayes)

    p_fc = sub.add_parser("forecast", help="Time-series forecast (exponential smoothing)")
    p_fc.add_argument("--series", required=True, help="Comma-separated numbers, oldest first")
    p_fc.add_argument("--periods", type=int, default=1)
    p_fc.add_argument("--method", default="auto", choices=["auto", "simple", "holt", "holt_winters"])
    p_fc.add_argument("--alpha", type=float, default=None)
    p_fc.add_argument("--beta", type=float, default=None)
    p_fc.add_argument("--gamma", type=float, default=None)
    p_fc.add_argument("--seasonal-periods", type=int, default=None, dest="seasonal_periods")
    p_fc.set_defaults(func=cmd_forecast)

    p_run = sub.add_parser("run", help="Run a JSON spec from file or stdin")
    p_run.add_argument("spec", help="Path to JSON spec, or '-' for stdin")
    p_run.set_defaults(func=cmd_run)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
