"""Decision optimizer — compare multiple options via Monte Carlo, rank them.

Given N option specs (each a full Monte Carlo spec), runs a simulation per
option and ranks by a user-defined objective over the outcome stats. Also
reports a Pareto frontier across multiple criteria.

Entry points:
    compare(options, objective=..., criteria=...) -> ranked result
    pareto_frontier(options, criteria) -> non-dominated options

CLI: `python -m engine.decision_optimizer options.yaml`
"""
from __future__ import annotations

import json
import sys
from typing import Any, Callable

from .monte_carlo import simulate


def _resolve_metric(report: dict, path: str) -> float:
    """Resolve a metric path like 'outcomes.net_value_usd.stats.mean'.

    Supports:
      outcomes.<name>.stats.<stat>          e.g. outcomes.cost.stats.p5
      outcomes.<name>.probability_true
      variables.<name>.<stat>
    """
    parts = path.split(".")
    node = report
    for p in parts:
        if not isinstance(node, dict) or p not in node:
            raise KeyError(f"metric path {path!r} not found; stopped at {p!r}")
        node = node[p]
    if not isinstance(node, (int, float)):
        raise ValueError(f"metric path {path!r} did not resolve to a number, got {type(node).__name__}")
    return float(node)


def compare(
    options: dict[str, dict],
    *,
    objective: str | Callable[[dict], float],
    trials: int | None = None,
    seed: int | None = None,
    maximize: bool = True,
) -> dict[str, Any]:
    """Run a simulation per option and rank by the objective.

    Args:
        options: dict of option_name -> spec_dict
        objective: either a metric path (string) or a callable(report) -> float
        trials: override trials for all options
        seed: override seed for all options (reproducible)
        maximize: True (default) ranks higher is better, False ranks lower is better

    Returns:
        {
            "objective": <description>,
            "results": [
                {"option": name, "score": float, "report": {...}},
                ...
            ],
            "winner": <name>,
            "runner_up": <name> or None,
            "margin": float  # winner score - runner_up score (absolute)
        }
    """
    if callable(objective):
        score_fn = objective
        obj_desc = getattr(objective, "__name__", "custom")
    else:
        path = objective
        def score_fn(rep, _p=path):
            return _resolve_metric(rep, _p)
        obj_desc = objective

    results = []
    for name, spec in options.items():
        # Clone spec lightly to inject trials/seed overrides
        spec_to_run = dict(spec)
        if trials is not None:
            spec_to_run["trials"] = trials
        if seed is not None:
            spec_to_run["seed"] = seed
        report = simulate(spec_to_run)
        score = score_fn(report)
        results.append({"option": name, "score": score, "report": report})

    results.sort(key=lambda r: r["score"], reverse=maximize)
    winner = results[0]["option"] if results else None
    runner_up = results[1]["option"] if len(results) > 1 else None
    margin = (results[0]["score"] - results[1]["score"]) if len(results) > 1 else 0.0
    if not maximize:
        margin = -margin

    return {
        "objective": obj_desc,
        "maximize": maximize,
        "results": results,
        "winner": winner,
        "runner_up": runner_up,
        "margin": margin,
    }


def pareto_frontier(
    options: dict[str, dict],
    criteria: list[dict],
    *,
    trials: int | None = None,
    seed: int | None = None,
) -> dict[str, Any]:
    """Find Pareto-optimal options across multiple criteria.

    criteria: list of {"path": str, "maximize": bool, "label": str (optional)}

    Returns:
        {
            "criteria": [...],
            "results": [
                {"option": name, "scores": {label: score}, "report": {...}, "pareto": bool},
                ...
            ],
            "frontier": [option_name, ...]
        }
    """
    results = []
    for name, spec in options.items():
        spec_to_run = dict(spec)
        if trials is not None:
            spec_to_run["trials"] = trials
        if seed is not None:
            spec_to_run["seed"] = seed
        report = simulate(spec_to_run)
        scores = {}
        normalized_scores = {}  # For Pareto dominance comparison
        for c in criteria:
            label = c.get("label", c["path"])
            val = _resolve_metric(report, c["path"])
            scores[label] = val  # Keep original value for output
            # Normalize: always treat as "higher is better" by negating if minimizing
            normalized_scores[label] = val if c.get("maximize", True) else -val
        results.append({"option": name, "scores": scores, "_normalized": normalized_scores, "report": report})

    # Compute Pareto dominance using normalized scores
    labels = [c.get("label", c["path"]) for c in criteria]
    for r in results:
        r["pareto"] = True
    for i, r in enumerate(results):
        for j, other in enumerate(results):
            if i == j:
                continue
            # `other` dominates `r` if other >= r on all criteria and > on at least one
            all_geq = all(other["_normalized"][l] >= r["_normalized"][l] for l in labels)
            any_gt = any(other["_normalized"][l] > r["_normalized"][l] for l in labels)
            if all_geq and any_gt:
                r["pareto"] = False
                break

    # Remove internal normalized scores before returning
    for r in results:
        del r["_normalized"]

    frontier = [r["option"] for r in results if r["pareto"]]
    return {
        "criteria": criteria,
        "results": results,
        "frontier": frontier,
    }


def render_comparison(result: dict) -> str:
    """Render a comparison result as ASCII text."""
    lines = []
    lines.append("=" * 70)
    lines.append(f"  DECISION COMPARISON — objective: {result['objective']} "
                 f"({'maximize' if result['maximize'] else 'minimize'})")
    lines.append("=" * 70)
    if not result["results"]:
        lines.append("  No options to compare.")
        lines.append("=" * 70)
        return "\n".join(lines) + "\n"
    max_name = max(len(r["option"]) for r in result["results"])
    for rank, r in enumerate(result["results"], 1):
        marker = "🏆" if rank == 1 else f" {rank}"
        lines.append(f"  {marker}  {r['option']:<{max_name}}   score = {r['score']:>,.2f}")
    lines.append("")
    if result["winner"] and result["runner_up"]:
        lines.append(f"  Winner: {result['winner']}   (margin over runner-up: {result['margin']:.2f})")
    lines.append("=" * 70)
    return "\n".join(lines) + "\n"


def render_pareto(result: dict) -> str:
    lines = []
    lines.append("=" * 70)
    lines.append("  PARETO FRONTIER")
    lines.append("=" * 70)
    labels = [c.get("label", c["path"]) for c in result["criteria"]]
    name_w = max(25, max((len(r["option"]) for r in result["results"]), default=20))
    header = "  " + f"{'option':<{name_w}}" + " | " + " | ".join(f"{l:>20}" for l in labels) + " | pareto"
    lines.append(header)
    lines.append("  " + "-" * (len(header) - 2))
    for r in result["results"]:
        mark = "★" if r["pareto"] else " "
        score_str = " | ".join(f"{r['scores'][l]:>20,.2f}" for l in labels)
        lines.append(f"  {r['option']:<{name_w}} | {score_str} |   {mark}")
    lines.append("")
    lines.append(f"  Frontier (★): {', '.join(result['frontier'])}")
    lines.append("=" * 70)
    return "\n".join(lines) + "\n"


def _main(argv):
    """CLI entry point.

    Expects a YAML file with shape:
      options:
        option_a: {trials: 10000, variables: ..., outcomes: ...}
        option_b: {...}
      objective: "outcomes.net_value.stats.mean"      # or criteria for Pareto
      maximize: true
      criteria:                                        # for --pareto
        - {path: "outcomes.net_value.stats.mean", maximize: true, label: "expected_value"}
        - {path: "outcomes.net_value.stats.p5", maximize: true, label: "worst_case"}
    """
    import argparse
    p = argparse.ArgumentParser(prog="decision_optimizer")
    p.add_argument("spec_file")
    p.add_argument("--trials", type=int, default=None)
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--pareto", action="store_true", help="use criteria list, compute Pareto frontier")
    p.add_argument("--format", choices=["text", "json"], default="text")
    args = p.parse_args(argv)

    raw = open(args.spec_file).read()
    try:
        import yaml
        doc = yaml.safe_load(raw)
    except ImportError:
        doc = json.loads(raw)

    options = doc["options"]

    if args.pareto:
        result = pareto_frontier(options, doc["criteria"], trials=args.trials, seed=args.seed)
        if args.format == "json":
            # strip report details to keep payload small
            slim = {**result, "results": [{k: v for k, v in r.items() if k != "report"} for r in result["results"]]}
            json.dump(slim, sys.stdout, indent=2, default=float)
        else:
            sys.stdout.write(render_pareto(result))
    else:
        result = compare(
            options,
            objective=doc.get("objective", "outcomes.net_value_usd.stats.mean"),
            trials=args.trials,
            seed=args.seed,
            maximize=doc.get("maximize", True),
        )
        if args.format == "json":
            slim = {**result, "results": [{k: v for k, v in r.items() if k != "report"} for r in result["results"]]}
            json.dump(slim, sys.stdout, indent=2, default=float)
        else:
            sys.stdout.write(render_comparison(result))
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
