"""Render Monte Carlo results as terminal-friendly ASCII output.

Public functions:
    render_report(report, samples=None) -> str
    render_histogram(samples, title="", width=50, height=10) -> str
    render_tornado(tornado_entries, title="") -> str
"""
from __future__ import annotations

import math
from typing import Any

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


BLOCKS = " ▁▂▃▄▅▆▇█"


def _samples_to_list(samples):
    if HAS_NUMPY and isinstance(samples, np.ndarray):
        return samples.tolist()
    return list(samples)


def render_histogram(samples, title: str = "", width: int = 50, height: int = 8) -> str:
    """Render a horizontal histogram with ASCII blocks."""
    data = _samples_to_list(samples)
    if not data:
        return f"{title}\n  (no data)\n"
    lo, hi = min(data), max(data)
    if lo == hi:
        return f"{title}\n  All samples = {lo:.4g}\n"

    bins = max(10, min(width, 60))
    counts = [0] * bins
    bin_width = (hi - lo) / bins
    for v in data:
        idx = int((v - lo) / bin_width)
        if idx >= bins:
            idx = bins - 1
        counts[idx] += 1
    max_count = max(counts) if counts else 1

    lines = []
    if title:
        lines.append(title)
        lines.append("─" * min(len(title), 70))

    # Top axis value label (left and right)
    for row in range(height, 0, -1):
        threshold = max_count * row / height
        line_chars = []
        for c in counts:
            if c >= threshold:
                # pick block density proportional to how far above threshold
                over = min(1.0, (c - threshold * 0.875) / max(threshold * 0.125, 1e-9))
                idx = min(len(BLOCKS) - 1, int(1 + over * 7))
                line_chars.append(BLOCKS[idx])
            else:
                line_chars.append(" ")
        lines.append("".join(line_chars))

    # x-axis ruler
    ruler_chars = ["-"] * bins
    lines.append("".join(ruler_chars))

    # Labels for min, mid, max
    def _fmt(v):
        if abs(v) >= 1000 or (abs(v) < 0.01 and v != 0):
            return f"{v:.2e}"
        return f"{v:.2f}"
    mid = (lo + hi) / 2
    label_line = [" "] * bins
    for val, pos in [(lo, 0), (mid, bins // 2), (hi, bins - 1)]:
        text = _fmt(val)
        start = max(0, min(bins - len(text), pos - len(text) // 2))
        for i, ch in enumerate(text):
            if start + i < bins:
                label_line[start + i] = ch
    lines.append("".join(label_line))
    return "\n".join(lines) + "\n"


def render_tornado(tornado_entries: list[dict], title: str = "Tornado (variable impact)") -> str:
    """Render a tornado plot showing variables ranked by correlation."""
    if not tornado_entries:
        return f"{title}\n  (no variables to rank)\n"
    lines = [title, "─" * min(len(title), 70)]
    max_name = max(len(e["variable"]) for e in tornado_entries)
    max_bar = 30
    for e in tornado_entries:
        corr = e["correlation"]
        bar_len = int(abs(corr) * max_bar)
        bar = "█" * bar_len if corr >= 0 else "▓" * bar_len
        impact = e["impact"]
        sign = "+" if corr >= 0 else "-"
        lines.append(f"  {e['variable']:<{max_name}}  {sign} {bar:<{max_bar}} r={corr:+.3f} [{impact}]")
    lines.append("")
    lines.append("  █ positive correlation  ▓ negative correlation")
    return "\n".join(lines) + "\n"


def render_stats_block(name: str, stats: dict, extra: dict | None = None) -> str:
    """Compact stats summary."""
    lines = [f"  {name}:"]
    # Handle categorical stats (from string choice variables)
    if stats.get("type") == "categorical":
        lines.append(f"    type=categorical  mode={stats['mode']!r}  unique={stats['unique_count']}")
        counts = stats.get("counts", {})
        if counts:
            top_items = sorted(counts.items(), key=lambda x: -x[1])[:5]
            counts_str = ", ".join(f"{k!r}: {v}" for k, v in top_items)
            lines.append(f"    counts={{ {counts_str} }}")
    else:
        # Numeric stats
        lines.append(
            f"    mean={stats['mean']:.3g}  median={stats['median']:.3g}  "
            f"stddev={stats['stddev']:.3g}"
        )
        lines.append(
            f"    P5={stats['p5']:.3g}  P25={stats['p25']:.3g}  "
            f"P50={stats['p50']:.3g}  P75={stats['p75']:.3g}  P95={stats['p95']:.3g}"
        )
        lines.append(f"    range=[{stats['min']:.3g}, {stats['max']:.3g}]")
    if extra and "probability_true" in extra:
        lines.append(f"    P(true) = {extra['probability_true']*100:.1f}%")
    return "\n".join(lines) + "\n"


def render_report(report: dict[str, Any], samples: dict[str, Any] | None = None, show_histograms: bool = True) -> str:
    """Render the full Monte Carlo report as ASCII text.

    report: dict returned by simulate()
    samples: optional dict returned by simulate_with_samples()'s 3rd element
             (maps outcome_name -> sample array). If provided, shows histograms.
    """
    lines = []
    lines.append("=" * 70)
    lines.append("  MONTE CARLO SIMULATION REPORT")
    lines.append("=" * 70)
    lines.append(f"  Trials: {report['trials']:,}"
                 f"{'  Seed: ' + str(report['seed']) if report['seed'] is not None else ''}")
    lines.append("")

    # Variables summary
    lines.append("─" * 70)
    lines.append("  INPUT VARIABLES")
    lines.append("─" * 70)
    for name, stats in report["variables"].items():
        lines.append(render_stats_block(name, stats))

    # Outcomes
    lines.append("─" * 70)
    lines.append("  OUTCOMES")
    lines.append("─" * 70)
    for name, entry in report["outcomes"].items():
        stats = entry["stats"]
        extra = {"probability_true": entry["probability_true"]} if "probability_true" in entry else None
        lines.append(render_stats_block(name, stats, extra))
        if show_histograms and samples and name in samples:
            lines.append(render_histogram(samples[name], title=f"  Distribution: {name}", width=60, height=6))
        if entry.get("tornado"):
            lines.append(render_tornado(entry["tornado"], title=f"  Variable impact on {name}"))

    lines.append("=" * 70)
    return "\n".join(lines) + "\n"


def save_matplotlib_charts(report: dict, samples: dict, outdir: str) -> list[str]:
    """Optionally save matplotlib charts to `outdir`. Returns list of saved file paths.

    Silently returns [] if matplotlib is not installed.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return []

    import os
    os.makedirs(outdir, exist_ok=True)
    saved = []

    for name, outcome_samples in samples.items():
        data = _samples_to_list(outcome_samples)
        if not data:
            continue
        stats = report["outcomes"][name]["stats"]
        is_categorical = "mode" in stats and "mean" not in stats
        if is_categorical:
            continue
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.hist(data, bins=60, color="#4a90d9", edgecolor="white")
        ax.axvline(stats["mean"], color="red", linestyle="--", label=f"Mean = {stats['mean']:.3g}")
        ax.axvline(stats["p5"], color="orange", linestyle=":", label=f"P5 = {stats['p5']:.3g}")
        ax.axvline(stats["p95"], color="orange", linestyle=":", label=f"P95 = {stats['p95']:.3g}")
        ax.set_title(f"Distribution: {name}")
        ax.set_xlabel(name)
        ax.set_ylabel("Frequency")
        ax.legend()
        path = os.path.join(outdir, f"histogram_{name}.png")
        fig.savefig(path, dpi=120, bbox_inches="tight")
        plt.close(fig)
        saved.append(path)

        # Tornado
        tornado = report["outcomes"][name].get("tornado", [])
        if tornado:
            fig, ax = plt.subplots(figsize=(8, max(3, 0.4 * len(tornado))))
            names = [t["variable"] for t in tornado]
            corrs = [t["correlation"] for t in tornado]
            colors = ["#d94a4a" if c < 0 else "#4a90d9" for c in corrs]
            ax.barh(names, corrs, color=colors)
            ax.set_xlabel("Correlation with outcome")
            ax.set_title(f"Variable impact on {name}")
            ax.axvline(0, color="black", linewidth=0.5)
            path = os.path.join(outdir, f"tornado_{name}.png")
            fig.savefig(path, dpi=120, bbox_inches="tight")
            plt.close(fig)
            saved.append(path)

    return saved
