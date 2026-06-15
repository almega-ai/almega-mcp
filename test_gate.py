# -*- coding: utf-8 -*-
"""Tests for the Almega delegation-frame engine.  Run:  pytest -q"""
import almega_gate as a
from almega_gate import Frame, Decision, decide


# ── the pure policy engine ──

def test_decide_block_wins():
    f = Frame("x", allow=["read"], block=["read"])  # block beats allow
    assert decide(f, "read", None, None)[0] is Decision.BLOCKED

def test_decide_allow():
    f = Frame("x", allow=["read", "search"])
    assert decide(f, "read", None, None)[0] is Decision.ALLOWED

def test_decide_require_approval():
    f = Frame("x", require_approval=["deploy"])
    assert decide(f, "deploy", None, None)[0] is Decision.AWAITING

def test_decide_default_approval_is_fail_safe():
    f = Frame("x", default="approval")
    assert decide(f, "unknown.kind", None, None)[0] is Decision.AWAITING

def test_decide_default_block():
    f = Frame("x", default="block")
    assert decide(f, "unknown.kind", None, None)[0] is Decision.BLOCKED

def test_payment_under_threshold_allowed():
    f = Frame("x", allow_categories=["api"], approve_above=50, monthly_limit=200)
    assert decide(f, "payment", "api", 12)[0] is Decision.ALLOWED

def test_payment_over_threshold_awaiting():
    f = Frame("x", allow_categories=["api"], approve_above=50, monthly_limit=200)
    assert decide(f, "payment", "api", 90)[0] is Decision.AWAITING

def test_payment_over_budget_blocked():
    f = Frame("x", allow_categories=["api"], approve_above=50, monthly_limit=200, spent=180)
    assert decide(f, "payment", "api", 40)[0] is Decision.BLOCKED

def test_payment_bad_category_blocked():
    f = Frame("x", allow_categories=["api"], approve_above=50, monthly_limit=200)
    assert decide(f, "payment", "retail", 10)[0] is Decision.BLOCKED


# ── the MCP tools / state machine ──

def setup_function(_):
    a.reset()

def _frame():
    a.set_frame("ops", allow=["read"], require_approval=["deploy", "payment"],
                block=["shell.exec"], allow_categories=["api"],
                approve_above=50, monthly_limit=200)

def test_request_needs_a_frame():
    assert "error" in a.request("nobody", "read", "x")

def test_request_records_in_ledger():
    _frame()
    a.request("ops", "read", "read a file")
    rows = a.ledger("ops")
    assert len(rows) == 1 and rows[0]["decision"] == "ALLOWED"

def test_pay_is_sugar_over_request():
    _frame()
    r = a.pay("ops", "openai.com", 12, "api")
    assert r["kind"] == "payment" and r["decision"] == "ALLOWED"

def test_allowed_payment_applies_spend():
    _frame()
    a.pay("ops", "openai.com", 12, "api")
    assert a.get_frame("ops")["spent"] == 12.0
    assert a.get_frame("ops")["remaining"] == 188.0

def test_held_payment_does_not_spend_until_approved():
    _frame()
    r = a.pay("ops", "vercel.com", 90, "api")   # over $50 → AWAITING
    assert r["decision"] == "AWAITING_YOU"
    assert a.get_frame("ops")["spent"] == 0.0    # nothing spent yet
    a.approve(r["id"])
    assert a.get_frame("ops")["spent"] == 90.0   # now it counts

def test_reject_blocks_a_held_action():
    _frame()
    r = a.request("ops", "deploy", "deploy to prod")
    assert r["decision"] == "AWAITING_YOU"
    out = a.reject(r["id"], "not now")
    assert out["action"]["decision"] == "BLOCKED"
    assert a.pending("ops") == []                # cleared from the inbox

def test_blocked_action_stays_blocked():
    _frame()
    r = a.request("ops", "shell.exec", "rm -rf /")
    assert r["decision"] == "BLOCKED"
    assert "error" in a.approve(r["id"])          # can't approve a blocked action

def test_pending_inbox_lists_only_awaiting():
    _frame()
    a.request("ops", "read", "ok")               # allowed
    a.request("ops", "deploy", "hold")           # awaiting
    a.request("ops", "shell.exec", "no")         # blocked
    assert [p["kind"] for p in a.pending("ops")] == ["deploy"]
