"""Calibration tracker: predictions vs. actuals over time.

This closes the loop on "is the spec any good?" — you record a predicted
probability now, then when reality arrives, you record what actually happened.
Over time, the Calibrator tells you whether your 70% confidence claims
come true ~70% of the time.

Storage: JSONL file. Each line is one prediction record. Append-only, so
git-friendly and easy to audit.

Scoring:
  - Brier score: mean squared error between predicted p and actual (0/1).
    Lower is better. 0 = perfect. 0.25 = uninformed (always guessing 50/50).
  - Reliability curve: bins predictions by confidence band and reports
    the actual hit rate in each bin. Tells you if you're over/underconfident.
  - Resolution: how varied your predictions are (calibrated but useless
    if every prediction is 0.5).

Usage:
    from engine.calibration import Calibrator
    cal = Calibrator("predictions.jsonl")
    cal.record_prediction(id="postgres-migration", predicted=0.055,
                          claim="should_migrate", spec_path="examples/.../spec.yaml")
    # ...months later...
    cal.record_outcome(id="postgres-migration", actual=False)
    print(cal.score())
"""
from __future__ import annotations

import json
import os
import time
from typing import Any


class Calibrator:
    def __init__(self, path: str):
        self.path = path
        self._records: list[dict[str, Any]] = []
        if os.path.exists(path):
            self._load()

    def _load(self):
        with open(self.path) as f:
            for line in f:
                line = line.strip()
                if line:
                    self._records.append(json.loads(line))

    def _save(self):
        with open(self.path, "w") as f:
            for r in self._records:
                f.write(json.dumps(r) + "\n")

    def record_prediction(
        self,
        id: str,
        predicted: float,
        claim: str,
        spec_path: str | None = None,
        trials: int | None = None,
        metadata: dict | None = None,
    ) -> dict:
        """Record a new prediction. `predicted` is P(claim is true), 0..1."""
        if not 0.0 <= predicted <= 1.0:
            raise ValueError(f"predicted must be in [0, 1], got {predicted}")
        if self._find(id):
            raise ValueError(f"prediction with id={id!r} already exists")
        record = {
            "id": id,
            "predicted": float(predicted),
            "claim": claim,
            "spec_path": spec_path,
            "trials": trials,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "actual": None,
            "resolved_at": None,
            "metadata": metadata or {},
        }
        self._records.append(record)
        self._save()
        return record

    def record_outcome(self, id: str, actual: bool, notes: str | None = None) -> dict:
        """Resolve a previously recorded prediction with the real outcome."""
        rec = self._find(id)
        if rec is None:
            raise ValueError(f"no prediction with id={id!r}")
        if rec["actual"] is not None:
            raise ValueError(f"prediction {id!r} already resolved")
        rec["actual"] = bool(actual)
        rec["resolved_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        if notes:
            rec["metadata"]["notes"] = notes
        self._save()
        return rec

    def _find(self, id: str) -> dict | None:
        for r in self._records:
            if r["id"] == id:
                return r
        return None

    def resolved(self) -> list[dict]:
        return [r for r in self._records if r["actual"] is not None]

    def pending(self) -> list[dict]:
        return [r for r in self._records if r["actual"] is None]

    def score(self) -> dict[str, Any]:
        """Return calibration metrics over all resolved predictions."""
        resolved = self.resolved()
        if not resolved:
            return {
                "resolved_count": 0,
                "pending_count": len(self.pending()),
                "message": "no resolved predictions yet — keep recording outcomes",
            }

        n = len(resolved)
        # Brier score: mean((p - actual)**2)
        brier = sum((r["predicted"] - (1.0 if r["actual"] else 0.0)) ** 2 for r in resolved) / n

        # Base rate (how often true at all)
        base_rate = sum(1 for r in resolved if r["actual"]) / n

        # Brier score reference: always-predict-base-rate
        brier_ref = base_rate * (1 - base_rate)  # variance of Bernoulli(base_rate)
        skill_score = 1 - brier / brier_ref if brier_ref > 0 else 0.0

        # Reliability: bin predictions into deciles, report hit rate per bin
        bins = [[] for _ in range(10)]
        for r in resolved:
            idx = min(int(r["predicted"] * 10), 9)
            bins[idx].append(r)
        reliability = []
        for i, b in enumerate(bins):
            if not b:
                continue
            avg_pred = sum(r["predicted"] for r in b) / len(b)
            hit_rate = sum(1 for r in b if r["actual"]) / len(b)
            reliability.append({
                "bin": f"{i*10}-{(i+1)*10}%",
                "count": len(b),
                "avg_predicted": round(avg_pred, 3),
                "actual_hit_rate": round(hit_rate, 3),
                "gap": round(hit_rate - avg_pred, 3),
            })

        # Resolution: variance of predictions (higher = more informative)
        mean_pred = sum(r["predicted"] for r in resolved) / n
        resolution = sum((r["predicted"] - mean_pred) ** 2 for r in resolved) / n

        # Confidence bias: are you systematically over/underconfident?
        # High-confidence (>=0.7) predictions: check hit rate
        hi_conf = [r for r in resolved if r["predicted"] >= 0.7]
        hi_conf_hit = (
            sum(1 for r in hi_conf if r["actual"]) / len(hi_conf) if hi_conf else None
        )
        hi_conf_avg = (
            sum(r["predicted"] for r in hi_conf) / len(hi_conf) if hi_conf else None
        )

        return {
            "resolved_count": n,
            "pending_count": len(self.pending()),
            "brier_score": round(brier, 4),
            "brier_reference": round(brier_ref, 4),
            "skill_score": round(skill_score, 4),
            "base_rate": round(base_rate, 3),
            "resolution": round(resolution, 4),
            "reliability_curve": reliability,
            "high_confidence_check": {
                "count": len(hi_conf),
                "avg_predicted": round(hi_conf_avg, 3) if hi_conf_avg else None,
                "actual_hit_rate": round(hi_conf_hit, 3) if hi_conf_hit else None,
                "gap": round(hi_conf_hit - hi_conf_avg, 3) if hi_conf_hit is not None else None,
            },
            "interpretation": _interpret(brier, brier_ref, skill_score, n),
        }

    def render(self) -> str:
        """ASCII report suitable for terminals."""
        s = self.score()
        lines = []
        lines.append("=" * 70)
        lines.append("  CALIBRATION REPORT")
        lines.append("=" * 70)
        if s["resolved_count"] == 0:
            lines.append(f"  {s['message']}")
            lines.append(f"  Pending: {s['pending_count']} predictions awaiting outcomes.")
            lines.append("=" * 70)
            return "\n".join(lines) + "\n"

        lines.append(f"  Resolved: {s['resolved_count']}   Pending: {s['pending_count']}")
        lines.append(f"  Base rate: {s['base_rate']:.1%}   (how often claims are true overall)")
        lines.append("")
        lines.append(f"  Brier score: {s['brier_score']}   (lower = better; 0 = perfect)")
        lines.append(f"  Reference:   {s['brier_reference']}   (always-guess-base-rate baseline)")
        lines.append(f"  Skill score: {s['skill_score']:+.3f}   (> 0 beats baseline, < 0 worse)")
        lines.append("")
        lines.append("  Reliability curve (by predicted probability bin):")
        lines.append("  bin          | count | avg pred | actual | gap")
        lines.append("  " + "-" * 55)
        for row in s["reliability_curve"]:
            gap = row["gap"]
            gap_str = f"{gap:+.3f}"
            if abs(gap) < 0.1:
                mark = "✓"
            elif gap > 0:
                mark = "↑ underconfident"
            else:
                mark = "↓ overconfident"
            lines.append(
                f"  {row['bin']:<12} | {row['count']:>5} | {row['avg_predicted']:>8.3f} | "
                f"{row['actual_hit_rate']:>6.3f} | {gap_str} {mark}"
            )

        hi = s["high_confidence_check"]
        if hi["count"]:
            lines.append("")
            lines.append(f"  High-confidence (≥70%) predictions: {hi['count']}")
            lines.append(
                f"    Avg predicted: {hi['avg_predicted']:.1%}   "
                f"Actual hit rate: {hi['actual_hit_rate']:.1%}   "
                f"Gap: {hi['gap']:+.3f}"
            )

        lines.append("")
        lines.append(f"  Interpretation: {s['interpretation']}")
        lines.append("=" * 70)
        return "\n".join(lines) + "\n"


def _interpret(brier: float, brier_ref: float, skill: float, n: int) -> str:
    if n < 10:
        return f"only {n} resolved predictions — need ~30+ for a stable calibration signal"
    if skill > 0.3:
        return "predictions are meaningfully better than guessing the base rate"
    if skill > 0.0:
        return "predictions beat the base-rate baseline, but only modestly"
    if skill > -0.3:
        return "predictions perform similarly to just guessing the base rate — spec quality is weak"
    return "predictions underperform the base rate — the spec may be systematically miscalibrated"


# CLI entry point
def _cli():
    import argparse
    ap = argparse.ArgumentParser(prog="engine.calibration", description="Track predictions vs actuals")
    ap.add_argument("--file", default="predictions.jsonl", help="Path to predictions JSONL store")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_rec = sub.add_parser("record", help="Record a new prediction")
    p_rec.add_argument("--id", required=True)
    p_rec.add_argument("--probability", type=float, required=True)
    p_rec.add_argument("--claim", required=True)
    p_rec.add_argument("--spec", default=None, help="Optional path to spec that produced this prediction")
    p_rec.add_argument("--trials", type=int, default=None)

    p_res = sub.add_parser("resolve", help="Resolve a prediction with actual outcome")
    p_res.add_argument("--id", required=True)
    p_res.add_argument("--actual", required=True, choices=["true", "false"])
    p_res.add_argument("--notes", default=None)

    sub.add_parser("score", help="Print calibration metrics")
    sub.add_parser("list", help="List all predictions")

    args = ap.parse_args()
    cal = Calibrator(args.file)

    if args.cmd == "record":
        rec = cal.record_prediction(
            id=args.id, predicted=args.probability, claim=args.claim,
            spec_path=args.spec, trials=args.trials,
        )
        print(f"recorded: {rec['id']} predicted={rec['predicted']:.3f} claim={rec['claim']!r}")
    elif args.cmd == "resolve":
        rec = cal.record_outcome(id=args.id, actual=args.actual == "true", notes=args.notes)
        print(f"resolved: {rec['id']} predicted={rec['predicted']:.3f} actual={rec['actual']}")
    elif args.cmd == "score":
        print(cal.render())
    elif args.cmd == "list":
        for r in cal._records:
            status = f"actual={r['actual']}" if r["actual"] is not None else "PENDING"
            print(f"  {r['id']:<30} p={r['predicted']:.3f} {status:<15} {r['claim']}")


if __name__ == "__main__":
    _cli()
