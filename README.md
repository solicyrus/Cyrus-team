# Cyrus Team — the Social Media Agent Team

Rebuilt 2026-10-27 on Cyrus's order, after a full audit of the old
code (the audit's verdict: the previous "team" in this repo was a
dead CrewAI demo plus a simulated robot manager, and the real daily
operation elsewhere was fragmented, mini-brained and loop-tainted).
The old files are preserved in `archive_old_agents/` as evidence;
nothing there is referenced by this system.

**Studio model:** Cyrus = boss (orders + final approval) ·
cyrus = manager (assigns, reviews, verifies) · the four senior
agents below = the workers.

## The team

| Agent | File | Job in one line |
|---|---|---|
| 🧠 **The Mastermind** | `smart_agents/strategist_agent.py` | Watches real trends (live search, sources recorded), designs the content calendar, and injects data-based — never guessed — video ideas. |
| 🎬 **The Content Director** | `smart_agents/director_agent.py` | Turns an idea into a publishable package: hook-first script, image/audio prompts, Imagen image, real Piper voice, and an ffmpeg render from distinct footage. |
| 🛠️ **The Core Developer** | `smart_agents/developer_agent.py` | The API hands: Telegram (working), YouTube Data API upload, Instagram photos/Reels, WhatsApp one-tap packages, and render-engine handling. |
| 🛡️ **The Strict QA** | `smart_agents/qa_agent.py` | The final guard: deterministic fact-scan, critic, and ffprobe media QA — with rejection power. Failing items are rejected with reasons and can never enter the publish queue. |

Each agent's دستور (charter, duties, red lines) is in
`smart_agents/README.md`.

## The pipeline

```
python main_pipeline.py run --topic "Vancouver Island travel"
```

Strategist → Director → Strict QA gate → publish queue
(`awaiting_approval`) → Cyrus approves → Developer publishes and
records the real per-channel results.

```
python main_pipeline.py status
python main_pipeline.py approve <entry-id>
python main_pipeline.py publish
```

## The laws (Cyrus, 2026-10-27 — enforced in code, not on paper)

- **Two states only:** really executed, or an honest «نمی‌شه» with
  the reason. Hallucination — pretending something was done — is
  forbidden, always.
- **No fake code, no fake rules.** Every function does its job or
  reports loudly why it cannot.
- **No looping, ever.** Renders use distinct real footage at honest
  lengths; insufficient footage is a loud failure, not a loop.
- **No invented facts.** The only approved product fact is
  Cyrus AI — CA$10 for 14 days. The deterministic fact-scan is the
  hard gate.
- **Videos are shown to Cyrus before publishing.** Uploads default
  to private; publishing happens only from the `approved` state.

## Credentials

Names only, in `.env.example`. Keys live in the environment, never
in this repo. What still needs credentials from Cyrus is listed in
`BUILD-REPORT.md` (the «نمی‌شه yet» list).
