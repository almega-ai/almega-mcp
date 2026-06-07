# 🧪 Almega MCP — the demonstrator

> A wallet & guardrail for AI agents, exposed as a Model Context Protocol
> > (MCP) server. Drop it into Claude Desktop, the Claude Agent SDK, or any
> > > MCP-compatible client, and your agent has a wallet with hard limits, a
> > > > human approval step, and a full ledger — instantly.
> > > > >
> > > > >> Ships with **two backends** out of the box:
> > > > >> >
> > > > >> >> - `memory` (default): everything in-process. Zero setup.
> > > > >> >> - > - `stripe`: real Stripe Issuing test-mode Cardholders + virtual Cards.
> > > > >> >>   > - >   No real money. You watch the dashboard light up live.
> > > > >> >>   >   >
> > > > >> >>   >   > ---
> > > > >> >>   >   >
> > > > >> >>   >   > ## Tools the server exposes
> > > > >> >>   >   >
> > > > >> >>   >   > | Tool | What it does |
> > > > >> >>   >   > |------|--------------|
> > > > >> >>   >   > | `open_wallet(agent_id, monthly_limit, allow, approve_above)` | Give an agent a wallet (and a real Stripe card if backend=stripe) |
> > > > >> >>   >   > | `pay(agent_id, merchant, amount, category)` | Agent tries to spend — gets `APPROVED`, `BLOCKED`, or `AWAITING_YOU` |
> > > > >> >>   >   > | `approve_pending(transaction_id)` | Human says yes to a held transaction |
> > > > >> >>   >   > | `reject_pending(transaction_id, reason)` | Human says no |
> > > > >> >>   >   > | `get_wallet(agent_id)` | Current balance & rules |
> > > > >> >>   >   > | `list_transactions(agent_id?, status?, limit)` | View the ledger |
> > > > >> >>   >   > | `reset()` | Wipe the local index (Stripe entities are kept) |
> > > > >> >>   >   >
> > > > >> >>   >   > Plus two resources: `almega://wallets` and `almega://ledger`.
> > > > >> >>   >   >
> > > > >> >>   >   > ---
> > > > >> >>   >   >
> > > > >> >>   >   > ## Install
> > > > >> >>   >   >
> > > > >> >>   >   > ```bash
> > > > >> >>   >   > pip install -r requirements.txt
> > > > >> >>   >   > ```
> > > > >> >>   >   >
> > > > >> >>   >   > Python 3.10+ recommended.
> > > > >> >>   >   >
> > > > >> >>   >   > ---
> > > > >> >>   >   >
> > > > >> >>   >   > ## Option A — Memory backend (30-second demo)
> > > > >> >>   >   >
> > > > >> >>   >   > No accounts, no env vars. Just run:
> > > > >> >>   >   >
> > > > >> >>   >   > ```bash
> > > > >> >>   >   > mcp dev almega_mcp.py     # opens the MCP Inspector
> > > > >> >>   >   > # or
> > > > >> >>   >   > python demo.py            # runs the Exhibit A scenario
> > > > >> >>   >   > ```
> > > > >> >>   >   >
> > > > >> >>   >   > ---
> > > > >> >>   >   >
> > > > >> >>   >   > ## Option B — Stripe Issuing test mode (5 minutes, still $0)
> > > > >> >>   >   >
> > > > >> >>   >   > The wallet maps to a **real Stripe Cardholder + virtual Card** and every
> > > > >> >>   >   > approved `pay()` creates a real **test-mode authorization**. You can open
> > > > >> >>   >   > the Stripe dashboard and see Almega's decisions reflected on Stripe live.
> > > > >> >>   >   >
> > > > >> >>   >   > ### Setup
> > > > >> >>   >   >
> > > > >> >>   >   > 1. Free Stripe account: <https://dashboard.stripe.com/register>
> > > > >> >>   >   > 2. 2. Activate Issuing in test mode: <https://dashboard.stripe.com/test/issuing/overview>
> > > > >> >>   >   >    3. 3. Grab your **TEST** secret key: <https://dashboard.stripe.com/test/apikeys>
> > > > >> >>   >   >      
> > > > >> >>   >   >       4. ### Run
> > > > >> >>   >   >      
> > > > >> >>   >   >       5. ```bash
> > > > >> >>   >   >          export STRIPE_SECRET_KEY=sk_test_...
> > > > >> >>   >   >          export ALMEGA_BACKEND=stripe
> > > > >> >>   >   >          python stripe_demo.py
> > > > >> >>   >   >          ```
> > > > >> >>   >   >
> > > > >> >>   >   > Almega refuses to start if your key isn't `sk_test_...` — there's no path
> > > > >> >>   >   > to accidentally hit live cards from this code.
> > > > >> >>   >   >
> > > > >> >>   >   > ### What you'll see in your Stripe dashboard
> > > > >> >>   >   >
> > > > >> >>   >   > - one virtual card per agent
> > > > >> >>   >   > - - every approved `pay()` as a real Stripe authorization on the card
> > > > >> >>   >   >   - - BLOCKED and AWAITING_YOU transactions stay at Almega's gate and never
> > > > >> >>   >   >     -   touch Stripe — exactly how it would behave in production
> > > > >> >>   >   >    
> > > > >> >>   >   >     -   ---
> > > > >> >>   >   >
> > > > >> >>   >   > ## Wire it into Claude Desktop
> > > > >> >>   >   >
> > > > >> >>   >   > ```json
> > > > >> >>   >   > {
> > > > >> >>   >   >   "mcpServers": {
> > > > >> >>   >   >     "almega": {
> > > > >> >>   >   >       "command": "python",
> > > > >> >>   >   >       "args": ["/absolute/path/to/almega_mcp.py"],
> > > > >> >>   >   >       "env": {
> > > > >> >>   >   >         "ALMEGA_BACKEND": "stripe",
> > > > >> >>   >   >         "STRIPE_SECRET_KEY": "sk_test_..."
> > > > >> >>   >   >       }
> > > > >> >>   >   >     }
> > > > >> >>   >   >   }
> > > > >> >>   >   > }
> > > > >> >>   >   > ```
> > > > >> >>   >   >
> > > > >> >>   >   > Restart Claude Desktop. Claude can now open wallets, attempt payments,
> > > > >> >>   >   > and ask you to approve sensitive ones.
> > > > >> >>   >   >
> > > > >> >>   >   > ---
> > > > >> >>   >   >
> > > > >> >>   >   > ## Demo prompt for Claude
> > > > >> >>   >   >
> > > > >> >>   >   > > Open a wallet for `research-bot` with a $50 monthly limit, allowing
> > > > >> >>   >   > > > `api` and `saas` categories, and requiring approval above $25. Then try:
> > > > >> >>   >   > > > >
> > > > >> >>   >   > > > >> 1. $12 to `openai.com` (api)
> > > > >> >>   >   > > > >> 2. > 2. $30 to `vercel.com` (saas)
> > > > >> >>   >   > > > >>    > 3. > 3. $800 to `luxury-store.io` (retail)
> > > > >> >>   >   > > > >>    >    > 4. >
> > > > >> >>   >   > > > >>    >    >    >> Show me the ledger.
> > > > >> >>   >   > > > >>    >    >    >>
> > > > >> >>   >   > > > >>    >    >    >> First approves, second held for sign-off, third blocked — exactly like
> > > > >> >>   >   > > > >>    >    >    >> the landing's "Exhibit A". On the Stripe backend, refresh
> > > > >> >>   >   > > > >>    >    >    >> <https://dashboard.stripe.com/test/issuing/authorizations> while it runs.
> > > > >> >>   >   > > > >>    >    >    >>
> > > > >> >>   >   > > > >>    >    >    >> ---
> > > > >> >>   >   > > > >>    >    >    >>
> > > > >> >>   >   > > > >>    >    >    >> ## Landing
> > > > >> >>   >   > > > >>    >    >    >>
> > > > >> >>   >   > > > >>    >    >    >> **<https://alemgaai.netlify.app>**
> > > > >> >>   >   > > > >>    >    >    >>
> > > > >> >>   >   > > > >>    >    >    >> ---
> > > > >> >>   >   > > > >>    >    >    >>
> > > > >> >>   >   > > > >>    >    >    >> ## License
> > > > >> >>   >   > > > >>    >    >    >>
> > > > >> >>   >   > > > >>    >    >    >> MIT.
> > > > >> >>   >   > > > >>    >    >    >> # Almega MCP — wallet & guardrail for AI agents
> > > > >> >>   >   > > > >>    >    >    >>
> > > > >> >>   >   > > > >>    >    >    >> The MCP server behind https://alemgaai.netlify.app
> > > > >> >>   >   > > > >>    >    >    >>
> > > > >> >>   >   > > > >>    >    >    >> Two backends ship in one file:
> > > > >> >>   >   > > > >>    >    >    >>
> > > > >> >>   >   > > > >>    >    >    >> - `python demo.py` — in-memory mode, 30 seconds, zero setup
> > > > >> >>   >   > > > >>    >    >    >> - - `python stripe_demo.py` — real Stripe Issuing test mode (free, $0)
> > > > >> >>   >   > > > >>    >    >    >>  
> > > > >> >>   >   > > > >>    >    >    >>   - Install: `pip install -r requirements.txt`
> > > > >> >>   >   > > > >>    >    >    >>  
> > > > >> >>   >   > > > >>    >    >    >>   - License: MIT.
> > > > >> >>   >   > > > >>    >    >    >>   - 
