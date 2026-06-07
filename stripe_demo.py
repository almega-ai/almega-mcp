"""
Almega + Stripe Issuing (test mode) — end-to-end demo

Runs the same "Exhibit A" scenario as demo.py, but with the Stripe backend.
After it runs, you can open the Stripe dashboard and SEE:

  - A real Cardholder named "Agent: research-bot"
  - A real virtual Card issued to it
  - The exact authorizations Almega created, marked APPROVED / DECLINED

No real money moves. Everything is test mode.

Setup once:
    1. Create a free Stripe account: https://dashboard.stripe.com/register
    2. Activate Issuing in test mode:
       https://dashboard.stripe.com/test/issuing/overview
       (Stripe asks for some business info even in test — fill what's there;
        nothing leaves test mode until you flip "Activate live")
    3. Grab your TEST secret key:
       https://dashboard.stripe.com/test/apikeys

Run:
    export STRIPE_SECRET_KEY=sk_test_...
    export ALMEGA_BACKEND=stripe
    python stripe_demo.py

Watch the dashboard while it runs:
    https://dashboard.stripe.com/test/issuing/cards
    https://dashboard.stripe.com/test/issuing/authorizations
"""

from __future__ import annotations

import os
import sys


def _check_env() -> None:
    missing = []
    if not os.environ.get("STRIPE_SECRET_KEY"):
        missing.append("STRIPE_SECRET_KEY")
    if os.environ.get("ALMEGA_BACKEND", "").lower() != "stripe":
        os.environ["ALMEGA_BACKEND"] = "stripe"
        print("(forced ALMEGA_BACKEND=stripe for this demo)\n")
    if missing:
        print("Missing env vars: " + ", ".join(missing))
        print("See the top of this file for setup instructions.")
        sys.exit(1)


def demo() -> None:
    _check_env()

    # Import after env is verified so make_backend() picks the right one
    from almega_mcp import (  # noqa: E402
        open_wallet,
        pay,
        approve_pending,
        get_wallet,
        list_transactions,
        ledger_resource,
        wallets_resource,
        backend,
    )

    print(f"=== Backend in use: {backend.name} ===\n")

    print("=== Opening a wallet for research-bot ===")
    print("(creates a Stripe Cardholder + virtual Card in test mode)")
    out = open_wallet(
        agent_id="research-bot",
        monthly_limit=50.0,
        allow=["api", "saas"],
        approve_above=25.0,
    )
    print(out)
    print()

    print("=== Attempt 1: $12 to openai.com (api) — should APPROVE ===")
    tx1 = pay("research-bot", "openai.com", 12.0, "api")
    print(tx1)
    print()

    print("=== Attempt 2: $30 to vercel.com (saas) — over approve_above, holds ===")
    tx2 = pay("research-bot", "vercel.com", 30.0, "saas")
    print(tx2)
    print()

    print("=== Attempt 3: $800 to luxury-store.io (retail) — wrong category ===")
    tx3 = pay("research-bot", "luxury-store.io", 800.0, "retail")
    print(tx3)
    print()

    print("=== Human approves the pending vercel.com charge ===")
    print(approve_pending(tx2["id"]))
    print()

    print("=== Final state ===")
    print(wallets_resource())
    print()
    print(ledger_resource())
    print()
    print("Open the Stripe dashboard to see the matching cardholder + card:")
    print("  https://dashboard.stripe.com/test/issuing/cards")
    print("And the matching authorizations:")
    print("  https://dashboard.stripe.com/test/issuing/authorizations")


if __name__ == "__main__":
    demo()
