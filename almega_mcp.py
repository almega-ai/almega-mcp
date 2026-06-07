"""
Almega MCP Server — a wallet & guardrail for AI agents

Drop this in as an MCP server and any MCP-compatible agent (Claude Desktop,
the Claude Agent SDK, custom agents, etc.) can:

    1. Open a wallet for itself with a budget & category rules
    2. Try to pay merchants — Almega enforces the rules
    3. Get blocked, approved, or held for human review

Two storage backends ship in this file:

  - ``memory`` (default): everything lives in-process. Great for a 30-second
    demo, no external accounts needed.

  - ``stripe``: every wallet maps to a real Stripe Issuing test-mode
    Cardholder + virtual Card. Every pay() creates a real test-mode
    authorization on Stripe. You see actual cards and ledgers in the Stripe
    dashboard. No real money moves.

Pick the backend via the ``ALMEGA_BACKEND`` env var (``memory`` or ``stripe``).

Install:
    pip install -r requirements.txt

Run with the MCP CLI:
    mcp dev almega_mcp.py

Or wire into Claude Desktop's config (see README.md).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Protocol

from mcp.server.fastmcp import FastMCP


# ──────────────────────────────────────────────────────────────────────────────
#  Domain model
# ──────────────────────────────────────────────────────────────────────────────

class Status(str, Enum):
    APPROVED = "APPROVED"
    BLOCKED = "BLOCKED"
    AWAITING_YOU = "AWAITING_YOU"


@dataclass
class Wallet:
    agent_id: str
    monthly_limit: float          # in dollars
    allow: list[str]              # categories the agent can spend in
    approve_above: float          # any single charge above this needs human ok
    spent_this_month: float = 0.0
    # Backend-specific identifiers, populated by the backend when relevant.
    cardholder_id: Optional[str] = None
    card_id: Optional[str] = None
    last4: Optional[str] = None


@dataclass
class Transaction:
    id: str
    agent_id: str
    merchant: str
    amount: float
    category: str
    status: Status
    reason: str
    created_at: str
    # Backend-specific identifier (Stripe authorization id, etc.)
    external_id: Optional[str] = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def decide(wallet: Wallet, amount: float, category: str) -> tuple[Status, str]:
    """The whole policy engine, on purpose tiny and readable."""
    if category not in wallet.allow:
        return Status.BLOCKED, f"category '{category}' is not in allow-list {wallet.allow}"

    remaining = wallet.monthly_limit - wallet.spent_this_month
    if amount > remaining:
        return Status.BLOCKED, (
            f"would exceed monthly limit (${amount:.2f} requested, "
            f"${remaining:.2f} left of ${wallet.monthly_limit:.2f})"
        )

    if amount > wallet.approve_above:
        return Status.AWAITING_YOU, (
            f"single charge above approval threshold "
            f"(${amount:.2f} > ${wallet.approve_above:.2f}) — held for human review"
        )

    return Status.APPROVED, "within budget, within rules"


# ──────────────────────────────────────────────────────────────────────────────
#  Backend protocol
# ──────────────────────────────────────────────────────────────────────────────

class Backend(Protocol):
    """Anything that can store/retrieve Almega state and (optionally) mirror
    decisions onto a real payments rail."""

    name: str

    def create_wallet(self, wallet: Wallet) -> None: ...
    def get_wallet(self, agent_id: str) -> Optional[Wallet]: ...
    def all_wallets(self) -> list[Wallet]: ...
    def record_transaction(self, tx: Transaction) -> None: ...
    def update_transaction(self, tx: Transaction) -> None: ...
    def get_transaction(self, tx_id: str) -> Optional[Transaction]: ...
    def list_transactions(self) -> list[Transaction]: ...
    def reset(self) -> None: ...


# ──────────────────────────────────────────────────────────────────────────────
#  Memory backend (default)
# ──────────────────────────────────────────────────────────────────────────────

class MemoryBackend:
    name = "memory"

    def __init__(self) -> None:
        self._wallets: dict[str, Wallet] = {}
        self._ledger: list[Transaction] = []
        self._next_tx_id: int = 1

    # internal id minting — only used by the MCP layer
    def next_tx_id(self) -> str:
        tx_id = f"tx_{self._next_tx_id:04d}"
        self._next_tx_id += 1
        return tx_id

    def create_wallet(self, wallet: Wallet) -> None:
        self._wallets[wallet.agent_id] = wallet

    def get_wallet(self, agent_id: str) -> Optional[Wallet]:
        return self._wallets.get(agent_id)

    def all_wallets(self) -> list[Wallet]:
        return list(self._wallets.values())

    def record_transaction(self, tx: Transaction) -> None:
        self._ledger.append(tx)

    def update_transaction(self, tx: Transaction) -> None:
        # Transactions are mutable references in MemoryBackend; nothing to do.
        return None

    def get_transaction(self, tx_id: str) -> Optional[Transaction]:
        for t in self._ledger:
            if t.id == tx_id:
                return t
        return None

    def list_transactions(self) -> list[Transaction]:
        return list(self._ledger)

    def reset(self) -> None:
        self._wallets.clear()
        self._ledger.clear()
        self._next_tx_id = 1


# ──────────────────────────────────────────────────────────────────────────────
#  Stripe Issuing backend (test mode only)
# ──────────────────────────────────────────────────────────────────────────────

class StripeBackend:
    """
    Real Stripe Issuing test-mode integration. Every wallet maps to a real
    Stripe Cardholder + virtual Card. Every pay() creates a real test-mode
    authorization. No money moves.

    Setup:
      1. https://dashboard.stripe.com/test/issuing — enable Issuing in test mode
      2. Export your test API key:  export STRIPE_SECRET_KEY=sk_test_...
      3. Set:                       export ALMEGA_BACKEND=stripe

    On first wallet creation, Almega:
      - creates a Cardholder ('Agent: <agent_id>') in test mode
      - issues a virtual Card to that cardholder
      - returns the last-4 so the agent knows its card

    On pay():
      - Almega's local policy decides APPROVED / BLOCKED / AWAITING_YOU
      - a real test-mode authorization is created on Stripe with that outcome
      - the Stripe dashboard shows the exact ledger Almega shows
    """

    name = "stripe"

    def __init__(self) -> None:
        api_key = os.environ.get("STRIPE_SECRET_KEY")
        if not api_key:
            raise RuntimeError(
                "ALMEGA_BACKEND=stripe but STRIPE_SECRET_KEY is not set. "
                "Export your test-mode key: sk_test_..."
            )
        if not api_key.startswith("sk_test_"):
            raise RuntimeError(
                "STRIPE_SECRET_KEY is not a TEST key. Almega refuses to run "
                "against live Stripe. Use sk_test_..."
            )
        try:
            import stripe  # type: ignore
            import requests  # type: ignore
        except ModuleNotFoundError as e:
            raise RuntimeError(
                "Missing dependencies. Run: pip install -r requirements.txt"
            ) from e
        stripe.api_key = api_key
        self.stripe = stripe
        self._api_key = api_key
        self._requests = requests

        # We still keep an in-process index so MCP lookups don't hammer Stripe.
        self._wallets: dict[str, Wallet] = {}
        self._ledger: list[Transaction] = []

    def _create_test_authorization(self, card_id: str, amount_cents: int, merchant: str) -> dict:
        """
        Test-helper endpoint to simulate a merchant authorization in test mode.
        Use raw HTTP so we don't depend on a specific stripe-python namespace
        layout (it has shifted across SDK versions).
        Docs: https://stripe.com/docs/api/issuing/authorizations/create_test_mode
        """
        resp = self._requests.post(
            "https://api.stripe.com/v1/test_helpers/issuing/authorizations",
            auth=(self._api_key, ""),
            data={
                "card": card_id,
                "amount": amount_cents,
                "currency": "eur",
                "merchant_data[name]": merchant,
                "merchant_data[category]": "computer_software_stores",
                "merchant_data[city]": "Internet",
                "merchant_data[country]": "FR",
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    # ---- wallets ----

    def create_wallet(self, wallet: Wallet) -> None:
        # Stripe Issuing's `name` field rejects numbers and special chars,
        # so we turn the agent_id into a clean letters-only display name and
        # stash the real id in metadata.
        import re
        import time
        parts = re.findall(r"[A-Za-z]+", wallet.agent_id)
        display = " ".join(p.capitalize() for p in parts) if parts else "Bot"
        stripe_name = f"Almega {display}"
        first_name = "Almega"
        last_name = "".join(parts).capitalize() or "Bot"

        # Stripe-friendly email: lowercase letters only, fall back to agent
        email_local = re.sub(r"[^a-z0-9_-]", "", wallet.agent_id.lower()) or "agent"

        # FR Issuing requires the cardholder to "accept" the issuing user terms,
        # passed as an IP+timestamp on cardholder creation.
        terms_acceptance = {
            "date": int(time.time()),
            "ip": "127.0.0.1",
        }

        ch = self.stripe.issuing.Cardholder.create(
            type="individual",
            name=stripe_name,
            email=f"{email_local}@almega.dev",
            phone_number="+33612345678",
            billing={"address": {
                "line1": "1 Rue Almega",
                "city": "Paris",
                "postal_code": "75001",
                "country": "FR",
            }},
            individual={
                "first_name": first_name,
                "last_name": last_name,
                "card_issuing": {
                    "user_terms_acceptance": terms_acceptance,
                },
            },
            metadata={"almega_agent_id": wallet.agent_id},
        )
        card = self.stripe.issuing.Card.create(
            cardholder=ch["id"],
            currency="eur",
            type="virtual",
            status="active",
        )
        wallet.cardholder_id = ch["id"]
        wallet.card_id = card["id"]
        try:
            wallet.last4 = card["last4"]
        except (KeyError, AttributeError):
            wallet.last4 = None
        self._wallets[wallet.agent_id] = wallet

    def get_wallet(self, agent_id: str) -> Optional[Wallet]:
        return self._wallets.get(agent_id)

    def all_wallets(self) -> list[Wallet]:
        return list(self._wallets.values())

    # ---- transactions ----

    def record_transaction(self, tx: Transaction) -> None:
        """
        Almega is the gate before Stripe. Only transactions Almega APPROVED
        actually reach Stripe — they show up as real test-mode authorizations
        on the card. BLOCKED and AWAITING_YOU transactions are held at the
        gate and never touch the card.

        In production this maps cleanly: Stripe sends a webhook on every
        merchant authorization, Almega decides in-flight, and Stripe finalizes
        from Almega's decision. Here in test mode we model the same idea
        without a webhook listener: Almega decides first, then mirrors only
        the green-lit transactions onto Stripe.
        """
        wallet = self._wallets.get(tx.agent_id)
        if wallet and wallet.card_id and tx.status is Status.APPROVED:
            amount_cents = int(round(tx.amount * 100))
            auth = self._create_test_authorization(wallet.card_id, amount_cents, tx.merchant)
            tx.external_id = auth["id"]
        # BLOCKED and AWAITING_YOU: no Stripe call. The card stays clean.
        self._ledger.append(tx)

    def update_transaction(self, tx: Transaction) -> None:
        """
        Called when a human approves/rejects a held transaction.
        On approval, NOW we send the tx through to Stripe — the gate opened.
        On rejection, nothing reaches Stripe.
        """
        if tx.status is not Status.APPROVED:
            return  # rejected — stays at the gate
        if tx.external_id:
            return  # already mirrored
        wallet = self._wallets.get(tx.agent_id)
        if not wallet or not wallet.card_id:
            return
        amount_cents = int(round(tx.amount * 100))
        auth = self._create_test_authorization(wallet.card_id, amount_cents, tx.merchant)
        tx.external_id = auth["id"]

    def get_transaction(self, tx_id: str) -> Optional[Transaction]:
        for t in self._ledger:
            if t.id == tx_id:
                return t
        return None

    def list_transactions(self) -> list[Transaction]:
        return list(self._ledger)

    def reset(self) -> None:
        # We don't delete Stripe entities — just forget the local index.
        self._wallets.clear()
        self._ledger.clear()


# ──────────────────────────────────────────────────────────────────────────────
#  Backend selection
# ──────────────────────────────────────────────────────────────────────────────

def make_backend() -> Backend:
    choice = os.environ.get("ALMEGA_BACKEND", "memory").lower()
    if choice == "memory":
        return MemoryBackend()
    if choice == "stripe":
        return StripeBackend()
    raise RuntimeError(
        f"Unknown ALMEGA_BACKEND={choice!r}. Use 'memory' or 'stripe'."
    )


backend: Backend = make_backend()

# tx id minting — works for both backends
_next_tx_id = 1


def _mint_id() -> str:
    global _next_tx_id
    tx_id = f"tx_{_next_tx_id:04d}"
    _next_tx_id += 1
    return tx_id


# ──────────────────────────────────────────────────────────────────────────────
#  MCP server
# ──────────────────────────────────────────────────────────────────────────────

mcp = FastMCP("Almega")


@mcp.tool()
def open_wallet(
    agent_id: str,
    monthly_limit: float,
    allow: list[str],
    approve_above: float = 25.0,
) -> dict:
    """
    Open a wallet for an agent.

    Args:
        agent_id: A stable id for the agent (e.g. "research-bot").
        monthly_limit: Max total spend per calendar month, in dollars.
        allow: List of allowed merchant categories (e.g. ["api", "saas"]).
        approve_above: Any single charge above this requires a human approval.

    Returns: the created wallet (including Stripe IDs if backend=stripe).
    """
    if backend.get_wallet(agent_id) is not None:
        return {"error": f"wallet for '{agent_id}' already exists"}
    w = Wallet(
        agent_id=agent_id,
        monthly_limit=float(monthly_limit),
        allow=list(allow),
        approve_above=float(approve_above),
    )
    backend.create_wallet(w)
    return {"ok": True, "backend": backend.name, "wallet": asdict(w)}


@mcp.tool()
def pay(
    agent_id: str,
    merchant: str,
    amount: float,
    category: str,
) -> dict:
    """
    Have an agent try to pay a merchant. Almega applies the rules and either
    approves the transaction, blocks it, or holds it for human approval.

    On the Stripe backend, a real test-mode authorization is created on the
    agent's virtual card so the outcome shows up in the Stripe dashboard.

    Returns the resulting transaction record.
    """
    wallet = backend.get_wallet(agent_id)
    if wallet is None:
        return {"error": f"no wallet for '{agent_id}'. Call open_wallet first."}

    status, reason = decide(wallet, float(amount), category)
    tx = Transaction(
        id=_mint_id(),
        agent_id=agent_id,
        merchant=merchant,
        amount=round(float(amount), 2),
        category=category,
        status=status,
        reason=reason,
        created_at=_now(),
    )
    if status is Status.APPROVED:
        wallet.spent_this_month = round(wallet.spent_this_month + tx.amount, 2)

    backend.record_transaction(tx)
    return asdict(tx)


@mcp.tool()
def approve_pending(transaction_id: str) -> dict:
    """
    Human approval for a transaction that was held (AWAITING_YOU).
    Marks it APPROVED and applies the spend to the wallet.
    """
    tx = backend.get_transaction(transaction_id)
    if tx is None:
        return {"error": f"no transaction with id {transaction_id}"}
    if tx.status is not Status.AWAITING_YOU:
        return {"error": f"transaction {transaction_id} is {tx.status}, not pending"}
    wallet = backend.get_wallet(tx.agent_id)
    if wallet is None:
        return {"error": f"wallet for '{tx.agent_id}' has disappeared"}
    tx.status = Status.APPROVED
    tx.reason = "approved by human"
    wallet.spent_this_month = round(wallet.spent_this_month + tx.amount, 2)
    backend.update_transaction(tx)
    return {"ok": True, "transaction": asdict(tx)}


@mcp.tool()
def reject_pending(transaction_id: str, reason: str = "rejected by human") -> dict:
    """Human rejection of a transaction held for approval."""
    tx = backend.get_transaction(transaction_id)
    if tx is None:
        return {"error": f"no transaction with id {transaction_id}"}
    if tx.status is not Status.AWAITING_YOU:
        return {"error": f"transaction {transaction_id} is {tx.status}, not pending"}
    tx.status = Status.BLOCKED
    tx.reason = reason
    backend.update_transaction(tx)
    return {"ok": True, "transaction": asdict(tx)}


@mcp.tool()
def get_wallet(agent_id: str) -> dict:
    """Get an agent's wallet — limits, spend so far, remaining budget."""
    wallet = backend.get_wallet(agent_id)
    if wallet is None:
        return {"error": f"no wallet for '{agent_id}'"}
    d = asdict(wallet)
    d["remaining"] = round(wallet.monthly_limit - wallet.spent_this_month, 2)
    d["backend"] = backend.name
    return d


@mcp.tool()
def list_transactions(
    agent_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """
    List recent transactions, optionally filtered.

    Args:
        agent_id: If provided, only that agent's transactions.
        status: One of APPROVED / BLOCKED / AWAITING_YOU. Case-insensitive.
        limit: Max number of transactions to return (most recent first).
    """
    rows = list(reversed(backend.list_transactions()))
    if agent_id is not None:
        rows = [t for t in rows if t.agent_id == agent_id]
    if status is not None:
        s = status.upper()
        rows = [t for t in rows if t.status.value == s]
    return [asdict(t) for t in rows[:limit]]


@mcp.tool()
def reset() -> dict:
    """Wipe all wallets and the ledger (local index only — Stripe entities are kept)."""
    global _next_tx_id
    backend.reset()
    _next_tx_id = 1
    return {"ok": True, "backend": backend.name}


# ──────────────────────────────────────────────────────────────────────────────
#  Resources (read-only views the agent / Claude can consult any time)
# ──────────────────────────────────────────────────────────────────────────────

@mcp.resource("almega://ledger")
def ledger_resource() -> str:
    """A printable view of the full ledger."""
    rows = backend.list_transactions()
    if not rows:
        return f"(empty ledger — no transactions yet · backend={backend.name})"
    lines = [f"Almega · Account Ledger · backend={backend.name}", "-" * 76]
    for tx in rows:
        ext = f"  [{tx.external_id}]" if tx.external_id else ""
        lines.append(
            f"{tx.id}  {tx.agent_id:<16}  → {tx.merchant:<22}  "
            f"${tx.amount:>8.2f}  {tx.status.value:<14}  {tx.reason}{ext}"
        )
    return "\n".join(lines)


@mcp.resource("almega://wallets")
def wallets_resource() -> str:
    """A printable view of all open wallets."""
    wallets = backend.all_wallets()
    if not wallets:
        return f"(no wallets opened yet · backend={backend.name})"
    lines = [f"Almega · Wallets · backend={backend.name}", "-" * 76]
    for w in wallets:
        remaining = w.monthly_limit - w.spent_this_month
        card = f"  card=•••• {w.last4}" if w.last4 else ""
        lines.append(
            f"{w.agent_id:<20}  limit=${w.monthly_limit:>8.2f}  "
            f"spent=${w.spent_this_month:>8.2f}  left=${remaining:>8.2f}  "
            f"allow={w.allow}  approve_above=${w.approve_above:.2f}{card}"
        )
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
