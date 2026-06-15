# -*- coding: utf-8 -*-
"""Proves the gateway gates the ACTION, not just the response: a held/blocked
tool's real side effect never happens until (and unless) you approve.  pytest -q"""
import almega_gate as core
import almega_gateway as gw

EFFECTS = []   # records real side effects, so we can assert they did/didn't happen


@gw.gated("read")
def read_file(path):
    return f"contents of {path}"

@gw.gated("file.delete")
def delete_file(path):
    EFFECTS.append(("delete", path))     # the real, dangerous side effect
    return f"deleted {path}"

@gw.gated("shell.exec")
def run_shell(cmd):
    EFFECTS.append(("shell", cmd))
    return "ran"


def setup_function(_):
    core.reset()
    gw._pending.clear()
    EFFECTS.clear()
    core.set_frame(gw.AGENT, allow=["read"],
                   require_approval=["file.delete"], block=["shell.exec"])


def test_allowed_runs_immediately():
    out = read_file("a.txt")
    assert out["almega"] == "ALLOWED"
    assert "contents of a.txt" == out["result"]


def test_awaiting_does_NOT_run_the_real_code():
    out = delete_file("prod.db")
    assert out["almega"] == "AWAITING_YOU"
    assert EFFECTS == []                  # nothing was deleted


def test_held_runs_only_after_approval():
    out = delete_file("prod.db")
    aid = out["action_id"]
    assert "error" in gw.run_pending(aid)  # can't run before approval
    assert EFFECTS == []
    res = gw.approve_and_run(aid)          # human approves → it runs
    assert res["almega"] == "RAN"
    assert EFFECTS == [("delete", "prod.db")]


def test_rejected_never_runs():
    out = delete_file("prod.db")
    core.reject(out["action_id"], "not that one")
    assert "error" in gw.run_pending(out["action_id"])
    assert EFFECTS == []                  # the delete never happened


def test_blocked_never_runs():
    out = run_shell("rm -rf /")
    assert out["almega"] == "BLOCKED"
    assert EFFECTS == []                  # shell never executed
