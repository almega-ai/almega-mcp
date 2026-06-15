# -*- coding: utf-8 -*-
"""The Gateway in action: a tool's real code can't run outside the frame.
Run: python demo_gateway.py"""
import almega_gate as core
import almega_gateway as gw

DELETED = []   # stands in for real, irreversible side effects


@gw.gated("read")
def read_file(path):
    return f"<contents of {path}>"

@gw.gated("file.delete")
def delete_file(path):
    DELETED.append(path)            # the dangerous part
    return f"deleted {path}"

@gw.gated("shell.exec")
def run_shell(cmd):
    DELETED.append(f"shell:{cmd}")
    return "ran"


core.reset()
core.set_frame(gw.AGENT,
               allow=["read"],
               require_approval=["file.delete"],
               block=["shell.exec"])

print("The agent calls tools. The real code only runs if the frame allows it.\n")

print("read_file('config.yaml')      ->", read_file("config.yaml")["almega"])

print("run_shell('rm -rf /')         ->", run_shell("rm -rf /")["almega"],
      " | deleted so far:", DELETED)

held = delete_file("customers.db")
print("delete_file('customers.db')   ->", held["almega"],
      " | deleted so far:", DELETED, " <- still nothing!")

print("\nYou review the held action and approve it:")
ran = gw.approve_and_run(held["action_id"])
print("approve_and_run(...)          ->", ran["almega"],
      " | deleted now:", DELETED, " <- only AFTER your OK")
