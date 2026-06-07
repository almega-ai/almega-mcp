"""
Almega MCP — a quick standalone demo that doesn't require Claude / an agent.

Runs the same scenario the landing shows as "Exhibit A", calling the server's
functions directly (no MCP transport). Useful to sanity-check the policy
engine.

Usage:
    python demo.py
    """

from almega_mcp import (
    open_wallet,
    pay,
    approve_pending,
    list_transactions,
    ledger_resource,
    wallets_resource,
)


def demo() -> None:
      print("\n=== Opening a wallet for research-bot ===")
      print(open_wallet(
          agent_id="research-bot",
          monthly_limit=50.0,
          allow=["api", "saas"],
          approve_above=25.0,
      ))

    print("\n=== Attempt 1: $12 to openai.com (api) ===")
    tx1 = pay("research-bot", "openai.com", 12.0, "api")
    print(tx1)

    print("\n=== Attempt 2: $30 to vercel.com (saas) — over approve_above ===")
    tx2 = pay("research-bot", "vercel.com", 30.0, "saas")
    print(tx2)

    print("\n=== Attempt 3: $800 to luxury-store.io (retail) — wrong category ===")
    tx3 = pay("research-bot", "luxury-store.io", 800.0, "retail")
    print(tx3)

    print("\n=== Human approves the pending vercel.com charge ===")
    print(approve_pending(tx2["id"]))

    print("\n=== Final state ===")
    print(wallets_resource())
    print()
    print(ledger_resource())


if __name__ == "__main__":
      demo()
  
