"""CLI + JSON-over-stdio interface for the Monte Carlo engine.

Examples:
    python -m engine run spec.yaml
    python -m engine run spec.yaml --trials 50000 --seed 7
    python -m engine run spec.yaml --format json
    cat spec.json | python -m engine run -
    python -m engine run spec.yaml --charts ./out/
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .monte_carlo import simulate_with_samples
from .visualize import render_report, save_matplotlib_charts


def _load_spec(path: str) -> dict:
    if path == "-":
        raw = sys.stdin.read()
    else:
        raw = Path(path).read_text(encoding="utf-8")
    raw = raw.strip()
    if not raw:
        raise ValueError("empty spec input")
    # Try JSON first (starts with { or [), else YAML
    if raw[0] in "{[":
        return json.loads(raw)
    try:
        import yaml
    except ImportError:
        raise ImportError(
            "YAML spec given but PyYAML not installed. "
            "Install with: pip install pyyaml  (or convert to JSON)"
        )
    return yaml.safe_load(raw)


def _samples_to_jsonable(samples_dict, max_samples_per_outcome=200):
    """Serialize outcome samples to JSON-friendly form (capped to avoid huge payloads).

    Handles both numeric and categorical (string) samples.
    """
    try:
        import numpy as np
        is_numpy = True
    except ImportError:
        is_numpy = False

    def _coerce(x):
        """Convert to JSON-serializable: float for numbers, str for strings."""
        if isinstance(x, str):
            return x
        try:
            return float(x)
        except (TypeError, ValueError):
            return str(x)

    out = {}
    for k, v in samples_dict.items():
        if is_numpy and hasattr(v, "tolist"):
            arr = v.tolist()
        else:
            arr = list(v)
        if len(arr) > max_samples_per_outcome:
            step = len(arr) / max_samples_per_outcome
            arr = [_coerce(arr[int(i * step)]) for i in range(max_samples_per_outcome)]
        else:
            arr = [_coerce(x) for x in arr]
        out[k] = arr
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="monte-carlo",
        description="Run a Monte Carlo simulation from a YAML/JSON spec.",
    )
    sub = parser.add_subparsers(dest="command")

    run_p = sub.add_parser("run", help="Run simulation from a spec file (or - for stdin)")
    run_p.add_argument("spec", help="path to YAML/JSON spec, or - for stdin")
    run_p.add_argument("--trials", type=int, default=None, help="override trials count")
    run_p.add_argument("--seed", type=int, default=None, help="override random seed")
    run_p.add_argument("--format", choices=["text", "json"], default="text",
                       help="output format (default text, json for machine consumption)")
    run_p.add_argument("--charts", metavar="DIR", default=None,
                       help="save matplotlib charts to DIR (requires matplotlib)")
    run_p.add_argument("--no-histograms", action="store_true", help="suppress ASCII histograms")
    run_p.add_argument("--include-samples", action="store_true",
                       help="include (downsampled) raw samples in JSON output")

    args = parser.parse_args(argv)

    if args.command != "run":
        parser.print_help()
        return 2

    try:
        spec = _load_spec(args.spec)
    except Exception as e:
        print(f"error loading spec: {e}", file=sys.stderr)
        return 1

    if args.trials is not None:
        spec["trials"] = args.trials
    if args.seed is not None:
        spec["seed"] = args.seed

    try:
        report, var_samples, outcome_samples = simulate_with_samples(spec)
    except Exception as e:
        print(f"simulation failed: {e}", file=sys.stderr)
        return 1

    if args.charts:
        try:
            paths = save_matplotlib_charts(report, outcome_samples, args.charts)
            if paths:
                report["charts"] = paths
            else:
                print("note: matplotlib not installed; skipped chart generation", file=sys.stderr)
        except Exception as e:
            print(f"warning: chart rendering failed: {e}", file=sys.stderr)

    if args.format == "json":
        payload = dict(report)
        if args.include_samples:
            payload["_samples"] = _samples_to_jsonable(outcome_samples)
        json.dump(payload, sys.stdout, indent=2, default=float)
        sys.stdout.write("\n")
    else:
        text = render_report(report, samples=outcome_samples, show_histograms=not args.no_histograms)
        sys.stdout.write(text)

    return 0


if __name__ == "__main__":
    sys.exit(main())
