<!-- mcp-name: io.github.almega-ai/almega-mcp -->

# 🛡️ Almega — the immutable delegation frame for AI agents

> **Delegate everything to your agents — within limits they can't cross.**
>
> Set the boundaries once. Your agent runs free inside them. Anything sensitive —
> spending money, deleting a file, deploying to prod, sending an email — pauses for
> a one-click human OK. Everything is logged. An MCP server, open source.

<p align="center">
  <img src="https://raw.githubusercontent.com/almega-ai/almega-mcp/main/almega-gate.gif" alt="An agent acts; Almega allows the safe actions, holds the sensitive ones for human approval, and blocks the dangerous ones — per an immutable frame" width="760">
</p>

---

## The problem: you want to delegate, not babysit

The whole point of an agent is to hand it the work and walk away. But the moment it acts on its own, it can spend money, touch production, delete data, call tools — and you have no real control over what it actually does.

The tempting fix is to put the rules *in the prompt*: "don't spend over $50, don't touch prod." **This does not hold.** A model honors an instruction right up until it's task-motivated not to — or until a prompt injection from a webpage overrides it, or a loop bug ignores it entirely. An instruction is a wish.

**The boundary has to live *outside* the agent — where a bug, an attack, or the agent itself can never talk its way past it.** That's Almega.

## How it works

A human sets the **frame** once (the agent has no tool to change it):

```python
set_frame(
    "ops-bot",
    allow=["read", "search"],                              # runs free
    require_approval=["payment", "deploy", "file.delete"], # pauses for you
    block=["shell.exec"],                                  # never
    default="approval",                                    # unknown action → ask you (fail-safe)
    monthly_limit=200, allow_categories=["api", "saas"], approve_above=50,  # payment sub-frame
)
```

Then the agent asks before anything sensitive — and Almega decides, outside it:

```python
request("ops-bot", "read",   "read config.yaml")            # → ALLOWED   (runs free)
request("ops-bot", "deploy", "deploy build #418 to prod")   # → AWAITING_YOU
request("ops-bot", "shell.exec", "rm -rf /")                # → BLOCKED
pay("ops-bot", "openai.com", 12, "api")                     # → ALLOWED   (under your cap)
pay("ops-bot", "vendor.io",  800, "retail")                # → BLOCKED   (off-frame)
```

Held actions wait for your one click:

```python
approve("act_0002")            # deploy → cleared to run
reject("act_0003", "not that database")
```

Every attempt — allowed, blocked, or held — lands in an append-only audit ledger.

## Payments are just one kind of guarded action

Almega started as a wallet for agents — per-agent spend limits + human approval, with a real **Stripe Issuing test-mode** backend (no real money). That wallet is still here: run `almega-wallet`. In the gate, `pay()` is built in as the flagship action — same gate, same approval flow. The point is that it guards **anything** you'd want a human in the loop for before it happens, not just money.

## The tools

| Tool | What it does |
|------|--------------|
| `set_frame` | Define an agent's immutable boundaries (operator only) |
| `request` | The gate — agent asks before a sensitive action → `ALLOWED` / `BLOCKED` / `AWAITING_YOU` |
| `pay` | Flagship payment example (sugar over `request`) |
| `approve` / `reject` | Human resolves a held action |
| `pending` | The approval inbox |
| `ledger` | The full audit log |
| `get_frame` | Inspect a frame + spend so far |

Plus resources: `almega://ledger`, `almega://frames`, `almega://pending`.

## Gate your own tools

Wrap any tool with `@gated` and its real code can't run outside the frame — the **action** is gated, not just the response:

```python
from almega_gateway import gated, approve_and_run

@gated("file.delete")
def delete_file(path): ...          # the dangerous part

delete_file("customers.db")          # → held; the file is NOT deleted
# ...you review and approve, then:
approve_and_run(action_id)           # → only now does it actually run
```

A blocked or unapproved call's side effect simply never happens. The transparent **Gateway** — drop Almega in front of any MCP server and auto-gate every tool, zero instrumentation — builds on this, and is next.

## Install

```bash
pip install almega-mcp        # or: uvx almega-mcp
```

Listed in the [official MCP registry](https://registry.modelcontextprotocol.io/v0/servers?search=io.github.almega-ai/almega-mcp) as `io.github.almega-ai/almega-mcp`. MIT.

## Why Almega, not the big players' stack

Stripe, Rain and AWS are building agent **payment** controls — closed, payment-only, locked to their platform. Almega is the opposite, on purpose:

- **Open-source & MCP-native** — your agent gets the gate as native tools, no glue.
- **Guards everything, not just money** — payments, tool calls, deletes, deploys, emails.
- **No vendor lock-in** — your control layer sits above any rail; swap the rail, keep Almega.

The thing that decides whether an agent *should* act shouldn't be owned by a single payment vendor.

## What's next (roadmap)

- **The Almega Gateway** — drop it in front of your other MCP tools and every sensitive call is auto-gated, no instrumentation. (This is the magic; the tools above are the foundation.)
- Persistence, an approval dashboard, team policies, audit export, SSO — the governance layer teams pay for.

Today it's a demonstrator (in-memory). The point is to make the model obvious in five minutes.

---

Building agents that actually do things? I'd love feedback on the frame model and the MCP surface — what would you want to gate, and what's missing?

*(Founding members get the hosted version — gateway + approval dashboard — at a founder rate locked for life: [alemgaai.netlify.app](https://alemgaai.netlify.app). The server above is free and yours to keep.)*
