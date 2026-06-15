# -*- coding: utf-8 -*-
"""
Almega Gateway — wrap any tool so it can't run outside the frame.

Put `@gated("file.delete")` on a tool and every call is checked against the
agent's immutable frame BEFORE the tool's real code runs:

  • ALLOWED      → it runs, returns the result, logged.
  • AWAITING_YOU → the call is HELD — the real code does NOT run. A human
                   approves, then `run_pending()` executes it.
  • BLOCKED      → denied. The real code never runs.

The point: a dangerous action (delete prod, wire money, run a shell command)
literally cannot happen until you say so — the side effect is gated, not just
the response. This is the foundation of the transparent Almega Gateway: drop it
in front of your tools and "should it?" is answered before "do it".

Reuses the frame engine in almega_gate.
"""
import functools
from typing import Optional

import almega_gate as core

AGENT = "agent"                    # single active agent for now; multi-agent later
_pending: dict[str, tuple] = {}    # action_id -> (fn, args, kwargs) held until approval


def gated(kind: str, summary: Optional[str] = None):
    """Wrap a tool function with the Almega frame. The wrapped tool returns a
    dict carrying the gate decision (and the real result only if it ran)."""
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            desc = summary or f"{fn.__name__}({', '.join(map(repr, args))})"
            rec = core.request(AGENT, kind, desc)
            if "error" in rec:
                return rec                                    # no frame set
            decision = rec["decision"]
            if decision == "ALLOWED":
                return {"almega": "ALLOWED", "result": fn(*args, **kwargs)}
            if decision == "AWAITING_YOU":
                _pending[rec["id"]] = (fn, args, kwargs)       # hold the real call
                return {"almega": "AWAITING_YOU", "action_id": rec["id"],
                        "message": f"Held for your approval: {desc}"}
            return {"almega": "BLOCKED", "reason": rec["reason"]}
        wrapper.__almega_kind__ = kind
        return wrapper
    return deco


def run_pending(action_id: str) -> dict:
    """Execute a held call — only if a human has approved it first."""
    rec = next((a for a in core._ledger if a.id == action_id), None)
    if rec is None:
        return {"error": f"no action {action_id}"}
    if rec.decision is not core.Decision.ALLOWED:
        return {"error": f"{action_id} is {rec.decision.value} — approve it first"}
    call = _pending.pop(action_id, None)
    if call is None:
        return {"error": f"{action_id} has no held call (already run?)"}
    fn, args, kwargs = call
    return {"almega": "RAN", "result": fn(*args, **kwargs)}


def approve_and_run(action_id: str) -> dict:
    """Convenience: a human approves a held action and runs it, in one step."""
    out = core.approve(action_id)
    if "error" in out:
        return out
    return run_pending(action_id)
