"""MCP server exposing the prediction toolkit as tools.

Any MCP-compatible client (Claude Code, web, Hermes, AEGIS, OpenClaw, etc.)
can connect and call these tools without needing Python dependencies
installed locally.

Tools exposed:
  - recommend_method: free-text → recommended family
  - bootstrap_ci: resample-based confidence interval
  - bayesian_probability_update: P(H|E) from prior + likelihoods
  - beta_binomial_update: conjugate update for rates
  - forecast_timeseries: exponential smoothing forecast

Start:
    python -m engine.mcp_server

Register with Claude Code via .mcp.json or your MCP client's config.
"""
from __future__ import annotations

import json
import sys
from typing import Any

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
    HAS_MCP = True
except ImportError:
    HAS_MCP = False

from . import (
    bootstrap_ci,
    beta_binomial_update,
    probability_update,
    forecast,
    recommend_method,
)


TOOLS = [
    {
        "name": "recommend_method",
        "description": (
            "Given a free-text problem description, recommend which of the 7 "
            "prediction method families fits best. Returns ranked candidates "
            "with reasoning. Use this FIRST before picking a specific tool."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "problem": {
                    "type": "string",
                    "description": "Free-text description of the prediction problem.",
                },
            },
            "required": ["problem"],
        },
    },
    {
        "name": "bootstrap_ci",
        "description": (
            "Bootstrap confidence interval for a statistic (mean, median, etc.). "
            "Use for small samples where you don't want to assume a distribution."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "data": {"type": "array", "items": {"type": "number"}},
                "stat": {"type": "string", "default": "mean",
                         "enum": ["mean", "median", "stdev", "variance", "min", "max", "sum"]},
                "n_resamples": {"type": "integer", "default": 10000},
                "ci": {"type": "number", "default": 0.95},
                "seed": {"type": "integer"},
            },
            "required": ["data"],
        },
    },
    {
        "name": "bayesian_probability_update",
        "description": (
            "Bayes' rule: P(H|E) = P(E|H)*P(H) / P(E). Use to update a single "
            "probability given new evidence (e.g. medical test results)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "prior": {"type": "number", "description": "P(H) before evidence, in [0,1]"},
                "likelihood_given_h": {"type": "number", "description": "P(E | H)"},
                "likelihood_given_not_h": {"type": "number", "description": "P(E | not H)"},
            },
            "required": ["prior", "likelihood_given_h", "likelihood_given_not_h"],
        },
    },
    {
        "name": "beta_binomial_update",
        "description": (
            "Conjugate Bayesian update for a rate/probability. Prior is Beta(alpha, beta); "
            "observed k successes out of n trials. Returns posterior distribution + CI. "
            "Perfect for A/B tests and small-sample rate estimation."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "alpha": {"type": "number", "description": "Prior alpha (≈successes + 1)"},
                "beta": {"type": "number", "description": "Prior beta (≈failures + 1)"},
                "successes": {"type": "integer"},
                "trials": {"type": "integer"},
            },
            "required": ["alpha", "beta", "successes", "trials"],
        },
    },
    {
        "name": "forecast_timeseries",
        "description": (
            "Forecast the next N periods of a time series via exponential smoothing. "
            "Supports simple (no trend), Holt (with trend), and Holt-Winters "
            "(trend + seasonality). Auto-picks method unless specified."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "series": {"type": "array", "items": {"type": "number"},
                           "description": "Historical observations, oldest first"},
                "periods": {"type": "integer", "default": 1},
                "method": {"type": "string", "default": "auto",
                           "enum": ["auto", "simple", "holt", "holt_winters"]},
                "alpha": {"type": "number"},
                "beta": {"type": "number"},
                "gamma": {"type": "number"},
                "seasonal_periods": {"type": "integer",
                                     "description": "Season length (12 for monthly yearly)"},
            },
            "required": ["series"],
        },
    },
]


def _dispatch(tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    if tool_name == "recommend_method":
        return recommend_method(args["problem"])
    if tool_name == "bootstrap_ci":
        return bootstrap_ci(
            data=args["data"], stat=args.get("stat", "mean"),
            n_resamples=args.get("n_resamples", 10000),
            ci=args.get("ci", 0.95), seed=args.get("seed"),
        )
    if tool_name == "bayesian_probability_update":
        return probability_update(
            prior=args["prior"],
            likelihood_given_h=args["likelihood_given_h"],
            likelihood_given_not_h=args["likelihood_given_not_h"],
        )
    if tool_name == "beta_binomial_update":
        return beta_binomial_update(
            alpha=args["alpha"], beta=args["beta"],
            successes=args["successes"], trials=args["trials"],
        )
    if tool_name == "forecast_timeseries":
        return forecast(
            series=args["series"], periods=args.get("periods", 1),
            method=args.get("method", "auto"),
            alpha=args.get("alpha"), beta=args.get("beta"), gamma=args.get("gamma"),
            seasonal_periods=args.get("seasonal_periods"),
        )
    raise ValueError(f"unknown tool: {tool_name}")


async def _run_server():
    server = Server("prediction-toolkit")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [Tool(**t) for t in TOOLS]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        try:
            result = _dispatch(name, arguments or {})
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def main():
    if not HAS_MCP:
        print(
            "MCP not installed. Install with: pip install mcp\n"
            "Or use CLI directly: python -m engine --help",
            file=sys.stderr,
        )
        sys.exit(1)
    import asyncio
    asyncio.run(_run_server())


if __name__ == "__main__":
    main()
