# Business Suite — White-Label Business Automation Agents

A sellable package of three AI agents for small and mid-size client
businesses. **One codebase, any business:** everything specific to a
client lives in a folder — `clients/<client-id>/` — holding a
`config.json` and a `knowledge/` folder. No code changes per client.

| Agent | What it does for the client |
|---|---|
| **Support** | Answers customer questions 24/7 **only from the client's own knowledge files**, in the client's brand tone. Captures leads (name/contact/need) into a local CRM store. |
| **Content** | Trend scan (sources labelled, never faked), a rotating content calendar, hook-first short-video scripts, captions and hashtags tuned to the client's niche. |
| **Workflow** | Reads the business inbox (emails/forms), classifies each message (order / appointment / question / spam), records orders and appointments, and writes a one-minute daily summary with an explicit "needs human action" list. |

Ships with a complete demo client, **`demo-dental`** (BrightSmile
Dental Studio), used by the demo runner and the whole test suite.

---

## Architecture map

```
business-suite/
├── business_suite/            # the importable package
│   ├── config.py              # client config loading + folder layout
│   ├── knowledge.py           # knowledge loading + inspectable keyword retrieval
│   ├── llm.py                 # THE thin LLM wrapper (only model gateway)
│   ├── crm.py                 # local CRM store (one JSON file per client)
│   ├── agents/
│   │   ├── support_agent.py   # grounded answers + lead capture
│   │   ├── content_agent.py   # trends, calendar, scripts, captions
│   │   └── workflow_agent.py  # inbox classify → records → daily summary
│   └── adapters/              # integration stubs (see "Not included yet")
│       ├── whatsapp.py  instagram.py  external_crm.py
├── prompts/                   # one system-prompt file per agent
│   ├── support_agent.md  content_agent.md  workflow_agent.md
├── clients/
│   └── demo-dental/           # config.json + knowledge/ + inbox/ samples
├── tests/                     # the proof suite (see below)
└── run_demo.py                # one-command demo on the demo client
```

### How the agents interact

- **Support ↔ Workflow:** both write into the same per-client CRM
  store (`clients/<id>/data/crm.json`) — Support adds *leads*,
  Workflow adds *orders* and *appointments*. One file the owner can
  open and read.
- **Workflow → Support (by design of the daily summary):** customer
  *questions* found in the inbox are listed under "Needs human
  action"; the same questions, asked on the website, are exactly
  what the Support Agent answers from knowledge. The summary shows
  the owner which questions keep recurring — a direct signal for
  which knowledge files to expand.
- **Content** is independent: it reads only `config.json` (niche,
  tone, pillars, services, hashtags) and optionally the LLM.
- **Everyone** talks to a model only through `llm.py`, and every
  agent result carries an honesty label: `grounded` true/false,
  `mode`/`generated_with` = `llm` or `deterministic`,
  classification `method` = `rules` / `llm-fallback` / `unresolved`.

### Grounding & honesty rules (the product's core promise)

1. Support answers are composed **only** from retrieved knowledge
   passages. If no passage matches, the agent refuses in the brand's
   voice and routes the customer to a human with the client's real
   contact details. It never invents a price, hour or policy.
2. Workflow classification is deterministic rules first; the LLM is
   a fallback for ambiguous messages only, and its reply must be
   strict JSON. Still unsure → `needs_review`, a human decides.
3. Adapters that are not wired for a client raise
   `NotConfiguredError` with the exact missing piece. Nothing in this
   package reports a success that did not happen.
4. With no API key, the agents run in **deterministic mode** and say
   so in their output labels. The demo and all tests run this way,
   with zero network.

---

## Quick start

Requirements: Python 3.10+, standard library only. (The LLM wrapper
uses `urllib`; no pip install is needed for the core package.)

```bash
cd business-suite

# Offline demo (deterministic, no key needed)
python3 run_demo.py

# Full proof suite
python3 -m unittest discover -s tests -v

# Optional: use a real model — set the key in the environment or in
# the repo-root .env (never commit a real .env)
export OPENAI_API_KEY=...
python3 run_demo.py --llm
```

The demo runs against a throwaway copy of the demo client; CRM
writes and reports never dirty the shipped fixture.

## Onboarding a new client (deployment checklist)

1. **Copy the folder:** `clients/demo-dental` → `clients/<new-id>`.
2. **Edit `config.json`:** business name, niche, tone, contacts,
   services, content pillars, trend seeds, signature hashtags.
   (Folder name must equal `client_id`.)
3. **Replace the knowledge files** with the client's real documents
   (services, prices, hours, FAQ, policies). Plain `.md`/`.txt`;
   one heading per topic works best — answers cite these files.
4. **Clear `inbox/`** and connect the client's message source
   (export/forward messages as `.txt` with `From:`/`Subject:`
   headers), or leave it for manual drops.
5. **Set the key:** `OPENAI_API_KEY` in the deployment environment
   (optional — deterministic mode works without it, with plainer
   phrasing).
6. **Run the proof suite** against the new folder before go-live,
   then schedule: Support on the website chat, Workflow once a day,
   Content once a week for the calendar.
7. **Wire channels per client** (see below) — each uses the
   *client's own* platform accounts and credentials.

## What is NOT included yet (honest list)

- **Live WhatsApp sending** — `adapters/whatsapp.py` is a stub. It
  needs the client's WhatsApp Business (Meta) credentials
  (`WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_ACCESS_TOKEN`) and a send
  implementation wired at deployment.
- **Live Instagram posting/DMs** — `adapters/instagram.py` is a
  stub (needs `IG_USER_ID`, `IG_ACCESS_TOKEN`, Meta app review).
- **External CRM sync (HubSpot/Salesforce)** —
  `adapters/external_crm.py` refuses pushes until a per-client field
  mapping is built. The local JSON CRM store is the working source
  of truth today.
- **Live trend measurement** — the Content Agent labels trend
  sources honestly (client seeds, service catalogue, LLM brainstorm).
  It does not scrape platforms or claim measured market data.
- **A hosted multi-tenant server** — this package is a per-client
  deployment (their folder, their keys, their machine/VPS), not a
  SaaS. Scheduling is via the host's cron/task scheduler.
- **Payments, booking-calendar sync, and email sending** — the
  Workflow Agent records appointment *requests* and writes reports;
  confirming bookings in a real calendar is a per-client integration.

## Pricing/deployment notes for selling

- Sell it as a **setup + monthly care** package: the setup is the
  onboarding checklist above (config, knowledge cleanup, channel
  wiring); monthly care covers knowledge updates, report review and
  prompt tuning.
- Each client deployment is isolated (own folder, own keys, own
  data) — a selling point for privacy-sensitive businesses.
- The proof suite doubles as the acceptance test in a client
  contract: it runs on *their* folder before go-live.
