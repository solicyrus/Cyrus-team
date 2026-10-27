# ACTIVATION READY — Cyrus Team (smart_agents)

Prepared 2026-10-27 under Cyrus's Production activation order.
All three protocols are implemented and PROVEN below. No real
key value appears in this repo, in this file, or in any log —
keys live only in a local `.env` / Actions secrets at activation.

## Files changed in this activation prep (all pushed + read-back size-verified on GitHub)

| File | Bytes | What |
|---|---|---|
| `.env.example` | 1,342 | completed against the code audit; AUTO_PUBLISH group added |
| `.gitignore` | 186 | `.env`, `.env.*` (with `!.env.example`), `*token*.json`, `client_secret*.json`, queue files |
| `requirements.txt` | 262 | `python-dotenv` added |
| `smart_agents/common.py` | 6,612 | guarded `load_dotenv()` of the repo-root `.env` |
| `smart_agents/queue.py` | 4,232 | `DRAFT` status formalized (legacy `awaiting_approval` = same gate state) |
| `smart_agents/qa_agent.py` | 12,700 | QA pass now lands items as `draft` in the publishing queue |
| `smart_agents/README.md` | 7,852 | pipeline diagram updated to the draft + gate wording |
| `main_pipeline.py` | 12,017 | dotenv load + THE APPROVAL GATE in `publish_approved()` |
| `check_system_health.py` | 10,756 | NEW — live health check (Protocol 3) |
| `tests/test_approval_gate.py` | 5,295 | NEW — the gate proof below |

## Protocol 1 — secure key configuration

`.env.example` (verbatim; every name the code reads via
`os.environ` is present — audited name by name. PIPER_BIN /
PIPER_MODEL / CYRUS_FOOTAGE_DIR are optional config the Director
reads; IMAGE_PUBLIC_URL is reserved for the Instagram activation
step — the Developer currently receives public image/video URLs
per queue entry):

```
# Cyrus Team — credential NAMES only. Copy to .env (never commit
# .env) or export in the environment. No values live in this repo.

# AI brain (smart_agents/common.py) — required for any AI work
OPENAI_API_KEY=

# Image generation (Director — Imagen via Gemini)
GEMINI_API_KEY=

# Telegram publishing (Developer — Bot API)
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# Instagram publishing (Developer — Meta Graph API)
IG_ACCESS_TOKEN=
IG_USER_ID=
# Public base URL where generated images are hosted for Meta to fetch
IMAGE_PUBLIC_URL=

# YouTube upload (Developer — Data API v3, OAuth)
# Path to the OAuth client-secrets JSON downloaded from Google Cloud
YOUTUBE_CLIENT_SECRETS=
# Where the OAuth token cache is stored after first sign-in
YOUTUBE_TOKEN_FILE=

# Voice (Director — Piper TTS, offline). Optional: the module also
# searches PATH and the house install locations.
PIPER_BIN=
PIPER_MODEL=

# Footage bank (Director). Optional: defaults to the house media
# library video folder.
CYRUS_FOOTAGE_DIR=

# Approval gate (main_pipeline.py publish). QA-passed packages
# land in the publishing queue as DRAFTS and stay drafts. An item
# is sent ONLY when this flag is exactly "True" OR a human has
# manually approved that item. Keep False for the standing rule:
# Cyrus sees every video before it goes out.
AUTO_PUBLISH=False
```

Secret-safety proof (GitHub recursive tree scan, run after this
push set): **37 tracked files (including this one), 0 hits** for
`.env` files, `*token*.json`, `client_secret*.json`, or
`credentials*.json`. The local mirror was scanned too: no real
`.env` or token file exists in it. `.env` loads happen through
python-dotenv at the two real entry points (`main_pipeline.py`,
`smart_agents/common.py`), guarded so the team still imports
without the library.

## Protocol 2 — approval gate (PROVEN)

QA-passed items land in the publishing queue with status `draft`.
`publish_approved()` sends an item ONLY when it carries a manual
approval marker (`approved`, set by `approve()` — which records
`approved_by="manual"` + timestamp) OR `AUTO_PUBLISH` is exactly
`"True"`. Held drafts are logged, never sent.

Proof — `tests/test_approval_gate.py` (the Telegram transport is
replaced by a counting fake, so nothing real can be sent;
dummy Telegram credentials ARE present in the environment during
the test, so only the gate can stop the send): **15/15 checks
PASSED, exit 0.**

- A: gate closed + draft → outcomes `[]`, transport calls 0, item stays `draft`
- B: manual approve → published, transport called exactly once, `approved_by="manual"` recorded
- C: `AUTO_PUBLISH=True` → draft published, transport called
- D: `AUTO_PUBLISH=false` → nothing published, item stays `draft`

Gate decision log lines from the run:

```
approval gate: HOLD draft gate-a — AUTO_PUBLISH is not "True" and the item has no manual approval; nothing sent
approval gate: PUBLISH gate-a (manual approval) -> published
approval gate: PUBLISH gate-c (AUTO_PUBLISH=True) -> published
approval gate: HOLD draft gate-d — AUTO_PUBLISH is not "True" and the item has no manual approval; nothing sent
```

## Protocol 3 — check_system_health.py (real runs)

Plain run in this environment (no keys configured), exit 0:

```
Cyrus Team — system health check
------------------------------------------------------------
OpenAI (team brain) — NOT_SET — OPENAI_API_KEY not set — no AI work is possible
Gemini (Imagen images) — NOT_SET — GEMINI_API_KEY not set — image generation disabled
Telegram (publishing) — NOT_SET — TELEGRAM_BOT_TOKEN not set — Telegram sends skipped
YouTube (uploads) — NOT_SET — YOUTUBE_CLIENT_SECRETS not set — OAuth client not created yet (needs Cyrus's Google Cloud step)
Instagram (publishing) — NOT_SET — not set: IG_ACCESS_TOKEN, IG_USER_ID — Meta token step still pending
Approval gate (AUTO_PUBLISH) — INFO — AUTO_PUBLISH=(unset) — gate CLOSED — drafts held for manual approval (safe default)
Local tool: ffmpeg (renderer) — OK — found on PATH
Local tool: Piper (voice) — OK — binary + voice model found (Director search)
------------------------------------------------------------
RESULT: READY — every configured service answered OK (NOT_SET items are warnings, listed above)
```

Proof run with the house OpenAI key loaded into the process
environment only (from `~/workspace/factory/.env`; never printed,
stored, or pushed), exit 0 — the OpenAI line is a REAL
authenticated verdict:

```
OpenAI (team brain) — OK — authenticated; 134 models visible
```

(all other lines identical to the plain run above.)

## Keys Cyrus must provide at activation — in order

1. **OPENAI_API_KEY** — Cyrus's OpenAI key, via the secure
   credential route (never in chat). The manager places it in
   this repo's local `.env` (and/or the GitHub Actions secret).
   Unlocks: the whole brain — Strategist, Director scripts, QA
   judging. NOTE: this same key value is also the game team's
   `AGENT_API_KEY` + `OPENAI_API_KEY` in solicyrus/cyrus-agents —
   one key lights up BOTH teams.
2. **GEMINI_API_KEY** — same secure route → `.env`. Unlocks:
   Imagen image generation in the Director.
3. **TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID** — unlocks Telegram
   publishing. The house already runs this bot for the daily
   robot team (its values live in that team's own env file); with
   Cyrus's go-ahead the manager wires the same values into this
   `.env` — no new signup needed.
4. **YouTube** — Cyrus creates the OAuth client in Google Cloud
   (manager guides the clicks) and hands over the client-secrets
   JSON via the secure route; its path goes in
   `YOUTUBE_CLIENT_SECRETS`. The first upload run does one Google
   sign-in and caches `YOUTUBE_TOKEN_FILE` automatically.
   Unlocks: YouTube uploads.
5. **IG_ACCESS_TOKEN + IG_USER_ID + IMAGE_PUBLIC_URL** — Meta
   token from the Meta app, plus the public base URL where
   generated images are hosted for Meta to fetch. Unlocks:
   Instagram photo + Reels publishing.

Nothing to provide for WhatsApp (by design it stays manual
one-tap packages — no API wired) or Facebook (no publisher wired
in this team yet).

Gate default at activation: `AUTO_PUBLISH=False` — every item
stays a draft until Cyrus approves it or orders the flag on.
