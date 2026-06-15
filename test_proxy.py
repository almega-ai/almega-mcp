# -*- coding: utf-8 -*-
"""Proves the transparent proxy gates BEFORE forwarding: an allowed call reaches
the downstream server; a blocked/held call never does.  pytest -q"""
import asyncio
from types import SimpleNamespace

import almega_gate as core
import almega_proxy as proxy
from mcp.server.fastmcp import FastMCP


class FakeSession:
    """Stands in for a real downstream MCP server, recording forwarded calls."""
    def __init__(self):
        self.calls = []

    async def list_tools(self):
        return SimpleNamespace(tools=[
            SimpleNamespace(name="read_file", description="read a file"),
            SimpleNamespace(name="delete_file", description="delete a file"),
            SimpleNamespace(name="run_shell", description="run a shell command"),
        ])

    async def call_tool(self, name, args):
        self.calls.append((name, args))
        return {"ok": True, "tool": name, "args": args}


def _build():
    core.reset()
    core.set_frame(proxy.PROXY_AGENT, allow=["read_file"],
                   require_approval=["delete_file"], block=["run_shell"])
    sess = FakeSession()
    srv = FastMCP("test-proxy")
    asyncio.run(proxy.attach(srv, sess))
    return srv, sess


def _call(srv, name, args):
    return asyncio.run(srv.call_tool(name, args))


def test_allowed_is_forwarded_downstream():
    srv, sess = _build()
    _call(srv, "read_file", {"arguments": {"path": "a.txt"}})
    assert sess.calls == [("read_file", {"path": "a.txt"})]


def test_blocked_never_reaches_downstream():
    srv, sess = _build()
    _call(srv, "run_shell", {"arguments": {"cmd": "rm -rf /"}})
    assert sess.calls == []


def test_awaiting_never_reaches_downstream():
    srv, sess = _build()
    _call(srv, "delete_file", {"arguments": {"path": "prod.db"}})
    assert sess.calls == []


def test_proxy_exposes_downstream_tools():
    srv, _ = _build()
    names = {t.name for t in asyncio.run(srv.list_tools())}
    assert {"read_file", "delete_file", "run_shell"} <= names
