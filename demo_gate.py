# -*- coding: utf-8 -*-
"""Scenario: one agent, one immutable frame, a stream of actions.
Run: python demo_gate.py"""
import almega_gate as a


def show(r):
    print(f"  {r['kind']:<13} {r['decision']:<12} {r['summary']}")


a.reset()

# A human sets the frame ONCE. The agent can't change it.
a.set_frame(
    "ops-bot",
    allow=["read", "search", "api.get"],                       # runs free
    require_approval=["payment", "email.send", "file.delete", "deploy"],  # needs a human
    block=["shell.exec"],                                       # never
    default="approval",                                         # unknown → ask
    monthly_limit=200, allow_categories=["api", "saas"], approve_above=50,
)

print("Agent acts. Almega decides — outside the agent:\n")
show(a.request("ops-bot", "read", "read config.yaml"))
show(a.request("ops-bot", "search", "search the docs for 'rate limit'"))
show(a.pay("ops-bot", "openai.com", 12, "api"))                # under threshold → ALLOWED
show(a.request("ops-bot", "deploy", "deploy build #418 to production"))  # AWAITING
show(a.request("ops-bot", "file.delete", "delete /var/data/customers.db"))  # AWAITING
show(a.pay("ops-bot", "vercel.com", 90, "saas"))               # over $50 → AWAITING
show(a.pay("ops-bot", "luxury-store.io", 800, "retail"))       # category not allowed → BLOCKED
show(a.request("ops-bot", "shell.exec", "rm -rf /"))           # BLOCKED
show(a.request("ops-bot", "browser.open", "open a URL it found"))  # unknown → default AWAITING

print("\nWaiting for you:")
for p in a.pending("ops-bot"):
    print(f"  [{p['id']}] {p['summary']}  — {p['reason']}")

print("\nYou approve the deploy, reject the delete:")
print(" ", a.approve("act_0004")["action"]["decision"], "deploy")
print(" ", a.reject("act_0005", "not that database")["action"]["decision"], "file.delete")

print("\n" + a.ledger_resource())
