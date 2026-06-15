# -*- coding: utf-8 -*-
"""
Almega — the immutable delegation frame for AI agents.

Set the boundaries once. Your agent runs free inside them. Anything sensitive
pauses for a one-click human OK. Everything is logged.

The whole point: the frame lives OUTSIDE the agent — so a bug, a prompt
injection, or the agent itself can never talk its way past it. Telling an agent
"don't do X" in its prompt is a wish. A frame it has to pass through is a wall.

Payments are just one kind of guarded action. So are sending an email, deleting
a file, deploying to prod, running a shell command — anything you'd want a human
in the loop for before it happens.

Exposed as an MCP server, so any agent gets the gate as native tools:

    pip install "mcp[cli]"
    mcp dev almega_gate.py
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from mcp.server.fastmcp import FastMCP


# ──────────────────────────────────────────────────────────────────────────────
#  Domain model
# ──────────────────────────────────────────────────────────────────────────────

class Decision(str, Enum):
    ALLOWED = "ALLOWED"            # runs free, within the frame
    BLOCKED = "BLOCKED"            # the frame forbids it
    AWAITING = "AWAITING_YOU"      # held for a one-click human approval


@dataclass
class Frame:
    """The immutable delegation frame for one agent.

    Set once, by a human/operator. The agent has NO tool to change its own
    frame — that's what makes the boundary immutable and the delegation safe.
    """
    agent_id: str
    allow: list[str] = field(default_factory=list)             # kinds that run free
    require_approval: list[str] = field(default_factory=list)  # kinds that need a human OK
    block: list[str] = field(default_factory=list)             # kinds always denied
    default: str = "approval"                                  # unknown kind: "approval" or "block"
    # Payment sub-frame — payments are one guarded kind, with budget semantics.
    monthly_limit: Optional[float] = None
    allow_categories: list[str] = field(default_factory=list)
    approve_above: Optional[float] = None
    spent: float = 0.0


@dataclass
class Action:
    id: str
    agent_id: str
    kind: str
    summary: str
    decision: Decision
    reason: str
    created_at: str
    category: Optional[str] = None
    amount: Optional[float] = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def decide(frame: Frame, kind: str, category: Optional[str], amount: Optional[float]) -> tuple[Decision, str]:
    """The whole policy engine — kept small and readable on purpose."""
    if kind in frame.block:
        return Decision.BLOCKED, f"'{kind}' is blocked by the frame"

    # Payments: budget + category + approval-threshold semantics.
    if kind == "payment":
        if frame.allow_categories and (category not in frame.allow_categories):
            return Decision.BLOCKED, f"category '{category}' not in allow-list {frame.allow_categories}"
        remaining = (frame.monthly_limit - frame.spent) if frame.monthly_limit is not None else math.inf
        if amount is not None and amount > remaining:
            return Decision.BLOCKED, (
                f"would exceed monthly limit (${amount:.2f} requested, ${remaining:.2f} left)"
            )
        if frame.approve_above is not None and amount is not None and amount > frame.approve_above:
            return Decision.AWAITING, (
                f"${amount:.2f} over the ${frame.approve_above:.2f} approval threshold — held for you"
            )
        return Decision.ALLOWED, "within budget, within rules"

    # Any other kind of action.
    if kind in frame.allow:
        return Decision.ALLOWED, f"'{kind}' runs free in this frame"
    if kind in frame.require_approval:
        return Decision.AWAITING, f"'{kind}' needs your one-click approval"

    # Unknown kind → the safe default.
    if frame.default == "block":
        return Decision.BLOCKED, f"'{kind}' isn't in the frame (default: block)"
    return Decision.AWAITING, f"'{kind}' isn't in the frame (default: human approval)"


# ──────────────────────────────────────────────────────────────────────────────
#  In-memory store (v1) — restart wipes it. Persistence comes later.
# ──────────────────────────────────────────────────────────────────────────────

_frames: dict[str, Frame] = {}
_ledger: list[Action] = []
_next_id = 1


def _mint() -> str:
    global _next_id
    aid = f"act_{_next_id:04d}"
    _next_id += 1
    return aid


# ──────────────────────────────────────────────────────────────────────────────
#  MCP server
# ──────────────────────────────────────────────────────────────────────────────

mcp = FastMCP("Almega")


@mcp.tool()
def set_frame(
    agent_id: str,
    allow: Optional[list[str]] = None,
    require_approval: Optional[list[str]] = None,
    block: Optional[list[str]] = None,
    default: str = "approval",
    monthly_limit: Optional[float] = None,
    allow_categories: Optional[list[str]] = None,
    approve_above: Optional[float] = None,
) -> dict:
    """Set the immutable delegation frame for an agent (an operator action — the
    agent cannot change its own frame).

    Args:
        agent_id: stable id for the agent (e.g. "ops-bot").
        allow: action kinds that run free, e.g. ["read", "search", "api.get"].
        require_approval: kinds that pause for a human, e.g.
            ["payment", "email.send", "file.delete", "deploy"].
        block: kinds always denied, e.g. ["shell.exec"].
        default: what to do with a kind not listed anywhere — "approval" (safe)
            or "block".
        monthly_limit / allow_categories / approve_above: the payment sub-frame.
    """
    f = Frame(
        agent_id=agent_id,
        allow=list(allow or []),
        require_approval=list(require_approval or []),
        block=list(block or []),
        default=default,
        monthly_limit=(float(monthly_limit) if monthly_limit is not None else None),
        allow_categories=list(allow_categories or []),
        approve_above=(float(approve_above) if approve_above is not None else None),
    )
    _frames[agent_id] = f
    return {"ok": True, "frame": asdict(f)}


@mcp.tool()
def request(
    agent_id: str,
    kind: str,
    summary: str,
    category: Optional[str] = None,
    amount: Optional[float] = None,
) -> dict:
    """The gate. An agent calls this BEFORE doing anything sensitive. Almega
    returns ALLOWED, BLOCKED, or AWAITING_YOU (held for a human), per the
    immutable frame. Every call is recorded in the audit ledger.

    Args:
        agent_id: the agent acting.
        kind: action type, e.g. "payment", "email.send", "file.delete",
            "deploy", "read".
        summary: a human-readable one-liner, e.g. "delete the prod database".
        category, amount: optional, used for payments.

    Returns the action record, including the decision.
    """
    frame = _frames.get(agent_id)
    if frame is None:
        return {"error": f"no frame for '{agent_id}'. Call set_frame first."}
    amt = float(amount) if amount is not None else None
    decision, reason = decide(frame, kind, category, amt)
    act = Action(
        id=_mint(), agent_id=agent_id, kind=kind, summary=summary,
        decision=decision, reason=reason, created_at=_now(),
        category=category, amount=amt,
    )
    if decision is Decision.ALLOWED and kind == "payment" and amt is not None:
        frame.spent = round(frame.spent + amt, 2)
    _ledger.append(act)
    return asdict(act)


@mcp.tool()
def pay(agent_id: str, merchant: str, amount: float, category: str) -> dict:
    """Flagship example: an agent tries to pay a merchant. Sugar over request()
    with kind="payment"."""
    return request(
        agent_id, "payment", f"pay {merchant} ${float(amount):.2f}",
        category=category, amount=amount,
    )


@mcp.tool()
def approve(action_id: str) -> dict:
    """Human approves a held action. Applies any spend and clears it to run."""
    for a in _ledger:
        if a.id == action_id:
            if a.decision is not Decision.AWAITING:
                return {"error": f"{action_id} is {a.decision.value}, not awaiting"}
            a.decision = Decision.ALLOWED
            a.reason = "approved by human"
            frame = _frames.get(a.agent_id)
            if frame and a.kind == "payment" and a.amount is not None:
                frame.spent = round(frame.spent + a.amount, 2)
            return {"ok": True, "action": asdict(a)}
    return {"error": f"no action {action_id}"}


@mcp.tool()
def reject(action_id: str, reason: str = "rejected by human") -> dict:
    """Human rejects a held action."""
    for a in _ledger:
        if a.id == action_id:
            if a.decision is not Decision.AWAITING:
                return {"error": f"{action_id} is {a.decision.value}, not awaiting"}
            a.decision = Decision.BLOCKED
            a.reason = reason
            return {"ok": True, "action": asdict(a)}
    return {"error": f"no action {action_id}"}


@mcp.tool()
def pending(agent_id: Optional[str] = None) -> list[dict]:
    """The approval inbox — actions waiting for a human's one-click decision."""
    rows = [a for a in _ledger if a.decision is Decision.AWAITING]
    if agent_id:
        rows = [a for a in rows if a.agent_id == agent_id]
    return [asdict(a) for a in rows]


@mcp.tool()
def ledger(agent_id: Optional[str] = None, limit: int = 50) -> list[dict]:
    """The audit log — every action attempted and what Almega decided (most
    recent first)."""
    rows = list(reversed(_ledger))
    if agent_id:
        rows = [a for a in rows if a.agent_id == agent_id]
    return [asdict(a) for a in rows[:limit]]


@mcp.tool()
def get_frame(agent_id: str) -> dict:
    """Inspect an agent's frame and spend so far."""
    frame = _frames.get(agent_id)
    if frame is None:
        return {"error": f"no frame for '{agent_id}'"}
    d = asdict(frame)
    if frame.monthly_limit is not None:
        d["remaining"] = round(frame.monthly_limit - frame.spent, 2)
    return d


@mcp.tool()
def reset() -> dict:
    """Wipe all frames and the ledger (local index only)."""
    global _next_id
    _frames.clear()
    _ledger.clear()
    _next_id = 1
    return {"ok": True}


# ── read-only views the human/agent can consult any time ──

@mcp.resource("almega://ledger")
def ledger_resource() -> str:
    if not _ledger:
        return "(empty ledger — no actions yet)"
    lines = ["Almega · Action Ledger", "-" * 78]
    for a in _ledger:
        amt = f"  ${a.amount:.2f}" if a.amount is not None else ""
        lines.append(
            f"{a.id}  {a.agent_id:<14}  {a.kind:<13}  {a.decision.value:<12}  {a.summary}{amt}"
        )
    return "\n".join(lines)


@mcp.resource("almega://frames")
def frames_resource() -> str:
    if not _frames:
        return "(no frames set yet)"
    lines = ["Almega · Delegation Frames", "-" * 78]
    for f in _frames.values():
        lines.append(
            f"{f.agent_id}:  free={f.allow}  approve={f.require_approval}  "
            f"block={f.block}  default={f.default}"
        )
    return "\n".join(lines)


@mcp.resource("almega://pending")
def pending_resource() -> str:
    rows = [a for a in _ledger if a.decision is Decision.AWAITING]
    if not rows:
        return "(nothing waiting for you)"
    lines = ["Almega · Awaiting your approval", "-" * 78]
    for a in rows:
        lines.append(f"{a.id}  {a.agent_id:<14}  {a.kind:<13}  {a.summary}  — {a.reason}")
    return "\n".join(lines)


def main() -> None:
    """Console entry point — runs the Almega gate over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
