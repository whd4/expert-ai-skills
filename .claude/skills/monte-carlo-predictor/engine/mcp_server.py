"""MCP server exposing the Monte Carlo engine as a tool.

Other agents that speak the Model Context Protocol (stdio-based) can call
`run_simulation` without knowing the engine internals.

Tools exposed:
    run_simulation(spec: object) -> object    # returns the full report dict
    describe_distribution(name: string) -> object   # docs for a distribution
    list_distributions() -> object

Run as:
    python -m engine.mcp_server

Requires the `mcp` Python package (optional):
    pip install mcp

If `mcp` is not installed, prints a helpful error and exits non-zero.
"""
from __future__ import annotations

import json
import sys


DISTRIBUTION_DOCS = {
    "uniform": {"params": ["low", "high"], "description": "Uniform distribution between low and high."},
    "normal": {"params": ["mean", "stddev"], "description": "Gaussian/normal distribution."},
    "triangular": {"params": ["low", "likely", "high"], "description": "Three-point estimation: best case, most likely, worst case."},
    "beta": {"params": ["alpha", "beta", "low?", "high?"], "description": "Beta distribution; optionally rescaled to [low, high]."},
    "lognormal": {"params": ["mean", "stddev"], "description": "Log-normal; mean/stddev are of the underlying normal."},
    "poisson": {"params": ["lam"], "description": "Poisson count distribution with rate lambda."},
    "choice": {"params": ["options", "weights?"], "description": "Discrete choice from a list, optionally weighted."},
    "constant": {"params": ["value"], "description": "Deterministic constant."},
}


def _import_mcp():
    try:
        from mcp.server import Server
        from mcp.types import Tool, TextContent
        from mcp.server.stdio import stdio_server
        return Server, Tool, TextContent, stdio_server
    except ImportError:
        print(
            "mcp package not installed. Install with: pip install mcp\n"
            "Or use the CLI/Python-API instead: python -m engine run spec.yaml",
            file=sys.stderr,
        )
        sys.exit(2)


def run_simulation_tool(arguments: dict) -> dict:
    """Entry point callable from any agent harness. Returns the report dict."""
    from .monte_carlo import simulate
    spec = arguments.get("spec")
    if spec is None:
        raise ValueError("run_simulation requires 'spec' argument")
    if isinstance(spec, str):
        # Agents can pass either a parsed dict or raw YAML/JSON string
        raw = spec.strip()
        if raw[0:1] in "{[":
            spec = json.loads(raw)
        else:
            try:
                import yaml
            except ImportError:
                raise ValueError("YAML spec passed but PyYAML not installed")
            spec = yaml.safe_load(raw)
    return simulate(spec)


async def _run_async():
    Server, Tool, TextContent, stdio_server = _import_mcp()
    server = Server("monte-carlo-predictor")

    @server.list_tools()
    async def _list_tools():
        return [
            Tool(
                name="run_simulation",
                description="Run a Monte Carlo simulation from a spec. Returns stats + tornado + P(true) for boolean outcomes.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "spec": {
                            "type": "object",
                            "description": "Simulation spec with trials, variables, outcomes. See schema docs.",
                        },
                    },
                    "required": ["spec"],
                },
            ),
            Tool(
                name="list_distributions",
                description="List available probability distributions and their parameters.",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="describe_distribution",
                description="Get parameter names and description for a named distribution.",
                inputSchema={
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                    "required": ["name"],
                },
            ),
        ]

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict):
        if name == "run_simulation":
            report = run_simulation_tool(arguments)
            return [TextContent(type="text", text=json.dumps(report, indent=2, default=float))]
        if name == "list_distributions":
            return [TextContent(type="text", text=json.dumps(DISTRIBUTION_DOCS, indent=2))]
        if name == "describe_distribution":
            dname = arguments.get("name")
            doc = DISTRIBUTION_DOCS.get(dname)
            if not doc:
                return [TextContent(type="text", text=json.dumps({"error": f"unknown: {dname}"}))]
            return [TextContent(type="text", text=json.dumps({dname: doc}, indent=2))]
        raise ValueError(f"unknown tool: {name}")

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main():
    import asyncio
    asyncio.run(_run_async())


if __name__ == "__main__":
    main()
