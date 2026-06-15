# -*- coding: utf-8 -*-
"""
Almega Proxy — the transparent gateway.

Sits in front of a downstream MCP server, re-exposes its tools, and gates every
call against the frame BEFORE forwarding:

  • ALLOWED      → forwarded to the real downstream tool.
  • AWAITING_YOU → held; the real tool is NOT called (a human approves later).
  • BLOCKED      → denied; the real tool is never called.

So you can drop Almega in front of ANY MCP server — a filesystem server, a
shell server, a payments server — and its dangerous tools instantly require
your say-so, with zero changes to that server.

`attach()` (the gating + forwarding core) is tested in-process against a fake
session in test_proxy.py. `run_proxy()` is the thin, standard SDK layer that
connects to a real downstream server over stdio.
"""
import almega_gate as core
from mcp.server.fastmcp import FastMCP

PROXY_AGENT = "agent"


def _make_forwarder(session, name, kind):
    """Build a gated async tool that forwards an allowed call to `session`.

    For the prototype the call takes an `arguments` dict. Mirroring the
    downstream tool's exact input schema (true transparency) is the next
    refinement — build the forwarder's signature from the tool's inputSchema."""
    async def forward(arguments: dict | None = None):
        args = arguments or {}
        rec = core.request(PROXY_AGENT, kind, f"{name}({args})")
        if rec.get("decision") == "ALLOWED":
            result = await session.call_tool(name, args)
            return {"almega": "ALLOWED", "result": result}
        if rec.get("decision") == "AWAITING_YOU":
            return {"almega": "AWAITING_YOU", "action_id": rec["id"],
                    "message": f"Held for your approval: {name}"}
        return {"almega": "BLOCKED", "reason": rec.get("reason", "blocked")}
    forward.__name__ = name
    return forward


async def attach(server: FastMCP, session, *, kind_of=None):
    """Discover `session`'s tools and register a gated forwarder for each on
    `server`. `session` needs async list_tools() and call_tool(name, args).
    `kind_of(tool_name)` maps a tool to an action kind (default: the name)."""
    kind_of = kind_of or (lambda n: n)
    listed = await session.list_tools()
    tools = getattr(listed, "tools", listed)
    for t in tools:
        name = t.name if hasattr(t, "name") else t["name"]
        desc = getattr(t, "description", None) or f"[gated via Almega] {name}"
        server.add_tool(_make_forwarder(session, name, kind_of(name)),
                        name=name, description=desc)
    return server


async def run_proxy(command: str, args=None):
    """Connect to a real downstream MCP server over stdio and serve the gated
    proxy. (Standard SDK transport layer — exercise against a live server.)"""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    server = FastMCP("Almega Proxy")
    params = StdioServerParameters(command=command, args=args or [])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            await attach(server, session)
            await server.run_stdio_async()
