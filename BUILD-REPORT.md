# BUILD REPORT — Cyrus Team Rebuild, 2026-10-27

Built to Cyrus's executive spec (issued 2026-10-27, superseding the
audit's folder layout): archive the old repo content, then build
exactly `smart_agents/` + `main_pipeline.py`. Every claim below was
verified by running the code or by GitHub read-back — nothing is
reported from intention.

## Final tree (GitHub read-back verified — every size matches local)

```
.env.example                                        1,020
.gitignore                                            110
README.md                                           2,925   (team page)
BUILD-REPORT.md                                     (this file — size verified on read-back)
requirements.txt                                      248
main_pipeline.py                                    9,611   (orchestrator)
smart_agents/
  README.md                                         7,806   (دستور — the four charters)
  __init__.py                                           0
  common.py                                         6,174   (support: logging + AI gateway)
  facts.py                                          9,785   (support: deterministic fact-scan)
  queue.py                                          3,640   (support: approval queue)
  channels.py                                       1,463   (support: channel registry)
  strategist_agent.py                              18,968   🧠 The Mastermind
  director_agent.py                                29,405   🎬 The Content Director
  developer_agent.py                               24,162   🛠️ The Core Developer
  qa_agent.py                                      12,631   🛡️ The Strict QA
archive_old_agents/
  README.md                                         1,043   (what the archive is, and why)
  main/py                                           4,673
  requirements.txt                                     24
  super-brain/  (.gitignore 42 · README.md 1,286 · api/__init__.py 14 ·
    api/server.py 1,454 · config.py 368 · core/__init__.py 15 ·
    core/brain.py 4,127 · core/llm.py 2,576 ·
    core/robot_manager.py 4,011 · core/task_scheduler.py 1,118 ·
    main.py 2,749 · requirements.txt 96 · robots/__init__.py 17 ·
    robots/real_robots.py 12,754 · robots/sample_robots.py 1,064)
```

**Archive step, exactly as ordered:** all 17 old files were first
pushed byte-for-byte under `archive_old_agents/` (sizes verified),
then the originals were removed via SHA-based contents-API deletes
(16 deletes). One exception, disclosed: the root `requirements.txt`
was overwritten in place with the new dependency list (HTTP 200) —
its original 24-byte content is preserved at
`archive_old_agents/requirements.txt`. **Correction to the spec's
assumption:** the old repo had NO root README (only
`super-brain/README.md`), so the new root `README.md` is a fresh
create, not an overwrite. No old-layout folders (`mastermind/`,
`content-director/`, `shared/`…) were ever pushed; local drafts were
deleted locally. The final tree contains nothing outside the spec.

## Reused vs new

**Reused from ultimate-robot-team (audit inventory, adapted with
credit comments):** the deterministic fact-scan
(`content_factory/fact_critic.py` → `facts.py`, incl. the approved
fact list and the strict `ca$10` token); the approval queue
(`robots/runner.py` → `queue.py`, atomic saves); the channels
registry (`brain/channels.py`); the DuckDuckGo watcher
(`robots/trend_watcher.py` → strategist signals); the Imagen image
maker (`robots/image_maker.py` → director); the Telegram publisher
contract (`robots/telegram_publisher.py` → developer).

**New:** the model-tier AI gateway with retry (`common.py`), the
content calendar, analytics-feedback honesty module, hook-first
script contract, Piper voice module, footage-bank planner with the
no-loop law in code, the ffmpeg renderer, the YouTube Data API
uploader, the Instagram photo/Reels publisher, the WhatsApp
one-tap package builder, media QA (ffprobe), the QA gate with
restored rejection power, and `main_pipeline.py`.

## Proof 1 — smoke suite (no-key honest mode): 40/40 PASS

`py_compile`: every `.py` in the push set compiles. The suite
(credentials scrubbed, so nothing could send) verified, among
others: fact-scan catches a planted `$25` price, invented `9 am`
hours and a phone number, passes the approved `CA$10 for 14 days`
copy, and catches `CA$100` (approved-token strictness); QA rejects
a fake-price package into `rejected` with reasons recorded and
passes a clean one into `awaiting_approval`; media QA flags a
corrupt file, a too-short video and a silent video, and passes a
real vertical video with audio; Piper synthesizes a real WAV
(3.24 s, measured) and fails LOUDLY when missing; the real footage
bank scans 65 clips / 62 usable / 1,448.8 s, exclusions enforced,
`plan(30)` uses distinct clips with `looping=False`, an impossible
plan raises instead of looping; a real render (2 distinct clips +
voice + music) measured 5.57 s at 1080×1920 with audio and passed
media QA; Telegram/YouTube/Instagram all report their honest
not-configured states; the Mastermind refuses ideas without
signals; live trend search returned real signals with URLs; the
pipeline dry-run in no-key mode ended in a loud, specific stage
failure — no fake package.

The suite also caught one real bug before shipping: the Piper
voice-model search glob pointed at `agents/*/piper/voices/` while
the house layout is `agents/*/voices/`. Fixed, re-proven.

## Proof 2 — END-TO-END DRY RUN through main_pipeline.py (real)

One sample run, using the OpenAI key from `~/workspace/factory/.env`
loaded into the run process only (never printed, logged, stored or
pushed — **disclosed honestly: the key was used for this sample
run**). Interpreter: the robot team's venv python (system python3
has no `openai` module — the first attempt failed loudly at the
ideas stage with exactly that reason, which is the designed
behaviour). All platform credentials were scrubbed: **nothing was
published**; the Developer stage stopped at the publish queue.

- **Strategist:** 10 real DuckDuckGo signals collected with source
  URLs → 2 grounded ideas: “Los Angeles vs. Barcelona: A Travel
  Showdown” and “Epic Grand Canyon Road Trip”.
- **Director:** real gpt-4o scripts (hook, title, caption,
  hashtags) + precise image and video prompts for both items.
  Image generation returned `None` — honestly: no Gemini key in
  the dry run, so no image was faked.
- **Render (Developer stage):** two REAL renders from house
  footage + Piper voice — 31.38 s and 33.01 s (30 s target covered
  by whole distinct segments; the renderer reports the true
  duration), both 1080×1920 with an audio stream.
- **QA:** both items PASSED (fact-scan clean; AI fact-critic notes
  recorded as warnings only; media QA passed on ffprobe facts) →
  queue status `awaiting_approval`.
- **POISONED ITEM (same run):** a copy of a passed package with
  “only $45 per person” planted in the caption → **REJECTED**,
  queue status `rejected`, reason recorded:
  `caption: unapproved money amount '$45'`.
- **Developer stage / publish gate:** `publish_approved()` returned
  `[]` — `awaiting_approval` is not `approved`, so nothing left
  the machine. Final queue: 2 awaiting_approval, 1 rejected.
  YouTube reports “not configured” loudly; Telegram without
  credentials returns a clean skip — nothing sent.

Full logs are kept with the manager (smoke-suite log + dry-run
log, 2026-10-27).

## «نمی‌شه yet» — the activation list (what each needs from Cyrus)

1. **Team OpenAI key placement.** The dry run borrowed the factory
   key for one sample run. Activation = put the team's own
   `OPENAI_API_KEY` in the run environment (secure route, never in
   chat, never in the repo). The success path of the retry wrapper
   is now proven live; a forced-failure retry was not staged.
2. **YouTube upload.** Needs a Google Cloud OAuth client
   (`YOUTUBE_CLIENT_SECRETS`) + a one-time sign-in by Cyrus; the
   token then caches locally. The uploader code is real and raises
   loudly until then. Uploads default to private (show-first rule).
3. **Instagram.** Needs a Meta access token + IG user id
   (`IG_ACCESS_TOKEN`, `IG_USER_ID`) and the public image-URL
   bridge (`IMAGE_PUBLIC_URL`) — Meta fetches media by URL, so
   local files are refused by design.
4. **WhatsApp.** No self-serve posting API is connected; the
   Developer builds the one-tap package file for Cyrus's phone.
   Full automation needs WhatsApp Business API + Meta business
   verification, done with Cyrus.
5. **Facebook.** Registry entry exists; no publishing code path is
   activated (page token + permissions needed from Cyrus).
6. **Imagen billing.** The image maker is real Google Imagen code
   via `GEMINI_API_KEY`; whether that key's billing covers Imagen
   in the team environment is unverified — the first activation run
   will show it, honestly, as success or as the API's own error.
7. **Platform analytics.** No YouTube/Instagram analytics are
   connected; the Strategist says so instead of inventing numbers,
   until those APIs are connected under items 2–3.
