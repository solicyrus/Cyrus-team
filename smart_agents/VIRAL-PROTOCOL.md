# VIRAL CONTENT ENGINE — FOREVER PROTOCOL

Standing structural order from Cyrus (the boss), issued
2026-10-27. This protocol is PERMANENT: it governs every daily
run of the smart_agents team until Cyrus himself replaces it.
It is wired into the agents' code (strategist, director, QA) —
this file is the human-readable charter; the code is the
enforcement.

## 0. ZERO-TOLERANCE POLICY

No shallow, copied, or low-quality content is accepted. Ever.

- Every package is ORIGINAL work by this team, grounded in real
  trend signals (never invented "trends").
- No invented prices, hours, phone numbers, or facts about
  places — the deterministic fact gate (facts.py) stays the
  hard-fail authority, unchanged by this protocol.
- A package that cannot meet the standard is REJECTED by QA,
  not shipped "good enough". Two-state rule: verified pass, or
  rejected with reasons.
- We never claim a video "will go viral". We score work against
  the formula below and report the score honestly.

## 1. DAILY VIRAL RESEARCH (Strategist — The Mastermind)

Every day, before production:

1. Analyse currently high-performing YouTube Shorts / Instagram
   Reels in the team's niche (travel; the day's destination),
   preferring videos with verifiable >1M views.
2. Extract the engagement formula actually used:
   - Hook type in the first 3 seconds (pattern interrupt,
     superlative, number/shock claim, secret reveal, question).
   - Pacing / cut rhythm (seconds per shot, cuts per beat).
   - Payoff moment (where the promise is cashed, and how late).
   - Loop device (how the ending connects back to the opening).
3. Record findings with source links in
   `smart_agents/research/YYYY-MM-DD-viral-patterns.md` and fold
   durable lessons into the living knowledge file
   `smart_agents/research/VIRAL-FORMULAS.md`, which the
   Strategist READS at the start of every idea run.

If a platform's data is unreachable on a given day, the research
says so plainly — yesterday's formulas are used and the gap is
reported. Research is never fabricated.

## 2. THE 30-SECOND GOLDEN FORMULA (Director — script law)

Every daily script is built on EXACTLY four timed beats:

| Beat | Time | Job |
|---|---|---|
| 1. THE HOOK | 0–3s | Visual + verbal pattern interrupt. Stops the thumb. A promise or shock the rest of the video must pay off. The hook line is the exact first spoken/on-screen line. |
| 2. THE TENSION / STORY | 3–15s | Fast narration, no filler. Builds a question or conflict in the viewer's mind. Every line raises the stakes or adds a new visual fact. |
| 3. THE CLIMAX | 15–25s | The answer, the unexpected reveal, the visual payoff the hook promised. |
| 4. THE LOOP & CTA | 25–30s | ONE decisive call to action, then the closing line is written so it flows directly back into the opening hook line — when the platform auto-replays the video, the sentence continues seamlessly (narrative seamless loop → watch time). |

The Director's script package carries these four beats as
structured fields (`beats.hook_0_3`, `beats.tension_3_15`,
`beats.climax_15_25`, `beats.loop_cta_25_30`) AND the full spoken
`script` assembled from them. A package missing any beat is
rejected by the Director itself.

**LOOP LAW (Cyrus, standing):** "Seamless loop" in this protocol
means the NARRATIVE loop above — words only. FOOTAGE LOOPING OR
PADDING IS FORBIDDEN FOREVER: renders use distinct real clips
from the footage bank (`looping=False`), as the footage planner
guarantees. A narrative loop never justifies a footage loop.

## 3. CINEMATIC PROMPT STANDARD (Director — reusable assets)

Alongside every script, the Director produces a shot-by-shot
list (one shot per beat minimum) where EVERY shot prompt is
ultra-detailed and cinematic, specifying:

- camera movement (e.g. slow push-in, gimbal glide, aerial orbit)
- cinematic lighting (source, direction, colour temperature feel)
- lens (focal character: wide 24mm feel, compressed 85mm feel…)
- texture / surface detail (what the eye should feel)
- exact subject motion
- composition for vertical 9:16

EVERY shot also carries a **negative prompt** (and the package
carries one global negative prompt) excluding: warped or
morphing subjects, deformed hands/faces, gibberish or warped
text, cartoon/CGI look, cheap stock-photo look, oversaturation,
flicker, watermark, logo artefacts.

These prompts are the reusable asset for external video models
(Sora / Runway / Kling / Luma class tools). Our own production
stays real-footage; the prompts never pretend to be media.

## 4. THE STRICT QA GATE — THE 4 QUESTIONS (QA — The Strict QA)

Before any package can be finalised, QA answers these four
questions LITERALLY, each with pass/fail + a stated reason,
recorded on the queue entry:

1. **Hook strength** — does the first-3-seconds hook have
   multi-million-view stopping power (pattern interrupt +
   clear promise)?
2. **Pacing** — do story and rhythm hold all the way to
   second 30 (no filler, tension maintained, climax lands at
   15–25s)?
3. **Prompt quality** — are the visual prompts genuinely
   cinematic and free of cheap/artificial effects (and do the
   negative prompts guard against them)?
4. **Loop integrity** — does the narrative loop actually work:
   does the final line connect back into the opening hook so a
   replay feels seamless?

A failed question (when the AI judge actually ran) REJECTS the
package, on top of the existing gates: the deterministic
fact-scan (invented prices/hours/phones = hard fail), the critic
score (reject below 4/10 when it ran), and media QA (ffprobe:
real vertical video, real duration, audio present). When the AI
judge is unavailable it ABSTAINS and says so — it never
fabricates a verdict.

## 5. SELF-EVOLUTION LOOP

- **Daily duty:** at least ONE complete package per day —
  research summary, 4-beat script, shot list, cinematic prompts
  + negative prompts, rendered video (real footage, Piper
  voice), QA verdicts — landing in the approval queue as a
  DRAFT. Publishing still requires Cyrus's approval (or
  AUTO_PUBLISH=True): the approval gate is NOT changed by this
  protocol.
- **Weekly evolution:** once a week the team reviews the week's
  packages and the newest global viral formulas, and UPDATES
  `smart_agents/research/VIRAL-FORMULAS.md` so each week's
  output standard is stronger and more current than the last.
- Packages are archived under
  `smart_agents/packages/YYYY-MM-DD-<topic>/`.

## 5b. CHANNEL NOTE — TIKTOK (reopened 2026-10-27, Cyrus's decision)

TikTok (@cyrusoutdoor) is a DISTRIBUTION channel again,
effective 2026-10-27, on these exact terms:

- **Distribution-only.** The daily package is cross-posted;
  there is NO separate TikTok growth work, no TikTok-specific
  content line, no engagement farming.
- **Manual one-tap.** No TikTok API/auto-post exists; Cyrus
  posts from his phone using the TikTok variant in each day's
  package (same vertical render + TikTok-written caption +
  hashtag set + on-screen cover text line;
  `developer_agent.tiktok_build_package`). The package as a
  whole stays behind the approval gate — a held draft is not
  cross-posted anywhere.
- **2-WEEK DATA TEST.** Start: 2026-10-27. **Kill criterion:**
  if the numbers are dead after ~2 weeks of daily posts
  (review on ~2026-11-10), the channel CLOSES again and this
  note is marked ended. Numbers are read honestly — no
  platform analytics feed is connected yet, so the review
  uses the figures TikTok itself shows Cyrus in-app.

## 6. DAILY TIME TABLE (America/Vancouver — proposed 2026-10-27, awaiting Cyrus's confirmation)

| Time | Stage | Owner |
|---|---|---|
| 07:30 | Daily viral research refresh (signals + pattern scan; Mondays: weekly formula evolution) | Strategist |
| 08:30 | Package production (ideas → 4-beat script → prompts → render) | Strategist → Director → Developer |
| 09:15 | QA gate (fact-scan + critic + 4-question viral checklist + media QA) | Strict QA |
| 09:30 | Draft ready in the approval queue for Cyrus's review | Pipeline |
| — | Publish ONLY after Cyrus approves (approval gate unchanged) | Developer |
