# DAILY PACKAGE — 2026-10-27 · LAS VEGAS

The Viral Content Engine's first package under the Forever
Protocol (smart_agents/VIRAL-PROTOCOL.md) — regenerated the
same day under Cyrus's protocol-compliance fix order.

- **Queue draft id: `77302239`** — status **draft**, held by
  the approval gate. NOTHING was published.
- Title: **Hidden Gems of the Las Vegas Strip**
- Video: `work/77302239/video.mp4` (repo workdir) — vertical
  1080×1920, audio present, **30.0s**, rendered from DISTINCT
  real footage bank clips (looping=False) + Piper voice
  (en_US-amy-medium).
- A second draft from the original run, `78b5e59b` ("TikTok's
  Influence on Young Vegas Travelers"), also passed QA and
  sits in the queue as a draft; this package documents the
  primary pick (the secret-reveal pattern, research pattern #6).

## Supersede record — draft `a4f904cd` → `77302239`

The original render measured **34.5s** against the protocol's
hard 30s formula. Cyrus's fix order (2026-10-27) tightened the
system, and this package was regenerated under it:

1. **Beat word budget (Director).** Piper's rate was measured
   from the 34.54s take (82 words → 2.374 words/second). Hard
   caps now enforced before rendering: hook ≤ 7, tension ≤ 28,
   climax ≤ 23, loop & CTA ≤ 11, full script ≤ 69 words — an
   over-budget script is rejected (one retry, then refused).
   The new script: 7 / 12 / 9 / 8 = **36 words**.
2. **Duration gate (QA).** ffprobe-measured duration is now a
   hard gate: **> 31s FAILS** the package, recorded on the
   verdict. New render: **30.0s — PASS**. (The old 34.5s video
   fails this gate today; verified directly.)
3. **Interpreter standard.** Pipeline entry points re-exec
   under the robot-team venv python instead of silently
   skipping the .env load (VIRAL-PROTOCOL.md §7).

Draft `a4f904cd` is marked **superseded** in
approval_queue.json with this reason and the new draft id —
history kept, nothing deleted. Its video stays on disk at
`work/a4f904cd/video.mp4` for the record.

**Honest note on the new take:** the writer over-corrected —
the voice runs 19.46s inside the 30.0s video (caps are
ceilings, and this script sits well under them). The package
meets the ordered standard (≤31s, all QA green) and the
shorter voice is recorded here rather than hidden; if Cyrus
wants a floor as well as a ceiling, that is a one-line budget
change for a future order.

## Research summary (full log: smart_agents/research/2026-10-27-viral-patterns.md)

Today's pattern stack, extracted from live research:

1. Hook = clarity + surprise in ONE line, strongest visual
   first (VegasStarfish's 2.0M-play MGM deal video; the
   Kallaway hook formula).
2. A concrete anchor — superlative, number, secret, or
   countdown (the 5M-view Sphere spectacle clip starts ON the
   payoff; the $13-Snickers video: 1.2M views in <24h on one
   prop + one number).
3. Middle = proof by showing, one new visual fact per line
   (monorail-savings reel; "7 Dumb Mistakes" countdown).
4. Payoff at 15–25s cashes exactly what the hook promised.
5. Close = one decisive CTA/question, then the narrative loop
   line re-enters the hook.

This package applies pattern #6 (secret reveal + how-to
promise) from the research log: hook "Secret spots on the Las
Vegas Strip!", step-like tension, mural/hidden-bar payoff,
CTA + hook re-entry as the loop.

## QA verdicts (full JSON: qa-verdict.json)

- Fact-scan (deterministic): PASS — no invented prices/hours/
  phones.
- Critic: 6.0/10 — "Strong hook and clear theme, but lacks a
  decisive ending." (Warning only; beat 4 carries the CTA
  "Discover more with Cyrus AI" — the critic judged it soft.)
- **Viral checklist (the Protocol's 4 questions) — ALL PASS:**
  1. Hook strength — PASS: "The hook 'Secret spots on the Las
     Vegas Strip!' is a clear promise and pattern interrupt."
  2. Pacing — PASS: "The pacing maintains tension and delivers
     a payoff with no filler."
  3. Prompt quality — PASS: "Visual prompts are cinematic with
     specific camera and lighting details, and negative prompts
     are included."
  4. Loop integrity — PASS: "The final line 'Secret spots
     await!' effectively loops back to the hook."
- Media QA (ffprobe): PASS — exists, readable, 1080×1920
  vertical, audio stream present, duration 30.0s.
- **Duration gate: PASS — measured 30.0s ≤ 31.0s max.**

## Contents

- `script.md` — beat sheet (with word counts vs budget) +
  full script + caption + hashtags
- `shots-and-prompts.md` / `prompts.json` — shot-by-shot
  cinematic prompts with per-shot + global negative prompts
- `qa-verdict.json` — the recorded QA verdict (incl.
  duration_gate)
- `tiktok-package.md` — TikTok variant (same render + TikTok
  caption + hashtags + cover text) for Cyrus's one-tap
  cross-post to @cyrusoutdoor; distribution-only, 2-week test
  (VIRAL-PROTOCOL.md §5b). NOT posted.
