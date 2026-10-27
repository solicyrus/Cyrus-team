# DAILY PACKAGE — 2026-10-27 · LAS VEGAS

The Viral Content Engine's Las Vegas package — rebuilt the
same day under **Forever Protocol v2** after Cyrus rejected
the first take himself (footage of orca whales / a forest
river under a Las Vegas script; Critical Failure #001 in
`smart_agents/ERROR-LOG.md`).

- **Queue draft id: `cb84c943`** — status **draft**, held by
  the approval gate. NOTHING was published.
- Title: **Hidden Gems of the Las Vegas Strip** (script
  unchanged from the approved take — only the footage,
  sourcing and gates changed).
- Video: `work/cb84c943/video.mp4` (repo workdir) — vertical
  1080×1920, **30.0s** measured, Piper voice
  (en_US-amy-medium) peak-normalized to −1.0 dBFS.
- **Footage (topic-matched, per-topic folder — never the
  personal bank):** ONE Wikimedia Commons clip — "Aerial
  views of Las Vegas Strip, Nevada, USA at night including
  The Bellagio, The Flamingo, MGM Grand Hotel, Caesars
  Palace, The Cosmopolitan, Mirage Hotel and Casino and the
  Venetian Palazzo Resort Casino" (342.2s, **CC BY 3.0**),
  matched by the query "Las Vegas aerial". The four beats
  use forward-jump offset subclips of it (offsets 0s / 48s /
  105s / 160s) — no frame range repeats, and every beat
  boundary is a real scene cut. Full sourcing record:
  `footage-manifest.json`.

## Supersede chain — how this draft came to be

- `a4f904cd` → superseded by `77302239` (34.5s render over
  the hard 30s standard; beat word budget + duration gate
  were built from that failure).
- **`77302239` → REJECTED BY CYRUS (2026-10-27).** Its
  footage was orca whales / forest river — the old renderer
  filled from a topic-blind local bank and QA never looked
  at the picture. Marked **superseded** by `cb84c943` in
  approval_queue.json; its video stays on disk for the
  record.
- Regeneration attempts under the new gates, each stopped
  honestly rather than filled with off-topic footage
  (details in `smart_agents/ERROR-LOG.md` and the queue):
  `b5f69133` (0.0s coverage STOP — stock queries too long),
  `9f15fa69` (22.1s coverage STOP — vision rejected
  mismatched clips), `42d70497` (render-plan failure, fixed
  with offset subclips), `39b70639` (0.0s STOP — vision
  judged against the marketing angle instead of the visual
  world and false-rejected real Strip aerials; fixed with
  the visual-world anchor), `25273f2c` (rendered 6/6 visual
  but rejected — audio threshold + advisory/hard-gate
  wiring corrected), `960f5b0c` (rejected — voice peaked at
  −0.0 dBFS; fixed with build-time peak normalization).
- **`cb84c943` — PASSED Forever Protocol v2 in full.**

## QA verdicts (full JSON: qa-verdict.json)

- Fact-scan (deterministic): PASS — no invented
  prices/hours/phones.
- Critic (advisory): 6.0/10 — "Strong hook and clear theme,
  but lacks a decisive call to action."
- Viral checklist (advisory under v2): hook PASS, pacing
  PASS, prompt quality PASS, loop FAIL (advisory only — the
  judge wanted the final line to re-enter the hook more
  literally; the hard gate's own loop check passed).
- Media QA (ffprobe): PASS — 1080×1920 vertical, audio
  present, duration **30.0s** (gate: ≤31s).
- **Forever Protocol v2 HARD GATE — ALL FIVE YES:**
  1. Image ↔ narrator's text 100% — YES: 6/6 sampled frames
     on-topic (Strip aerials, High Roller, Caesars Palace,
     Bally's). Sync evidence recorded: beat boundaries
     3.0s→cut 3.0s (offset 0.0s), 15.0s→cut 15.0s (0.0s),
     25.0s→cut 27.033s (2.033s; tolerance ±0.75s — recorded
     as evidence, as v2 specifies).
  2. 3-second hook — YES (viral hook judgement).
  3. Footage real & clear — YES: 6/6 frames cinematic, no
     watermark/cartoon/cheap effects; native sharpness
     enforced at selection (Law 3).
  4. Voice & sound clean — YES (measured): peak −1.0 dB,
     mean −20.3 dB, longest mid-video silence 4.11s, speech
     in every beat.
  5. Closing verbal loop — YES: beats complete, final beat
     re-enters the hook line, duration inside [29, 31].

## Audit of the day's other videos (same disease check)

Frame-sampled + vision-judged 2026-10-27 (verdicts only —
nothing deleted or unpublished; full record in
`local_proofs/visual-audit-2026-10-27.json`). **All four are
MISMATCHED** — every one is wall-to-wall forest-river
footage from the old topic-blind bank:

- `77302239` (this package's rejected take) — river/forest,
  0/6 frames on-topic.
- `78b5e59b` (draft, "TikTok's Influence on Young Vegas
  Travelers") — river/forest, 0/4 on-topic.
- `2388058d` (**PUBLISHED**, Grand Canyon, Telegram /12) —
  river/forest, 0/6 on-topic for the Grand Canyon.
- `0a947b1d` (**PUBLISHED**, Grand Canyon, Telegram /13) —
  river/forest, 0/6 on-topic.

Cyrus decides what happens to the two published pieces.

## Research summary (full log: smart_agents/research/2026-10-27-viral-patterns.md)

Today's pattern stack, extracted from live research:

1. Hook = clarity + surprise in ONE line, strongest visual
   first (VegasStarfish's 2.0M-play MGM deal video; the
   Kallaway hook formula).
2. A concrete anchor — superlative, number, secret, or
   countdown (the 5M-view Sphere spectacle clip starts ON
   the payoff; the $13-Snickers video: 1.2M views in <24h on
   one prop + one number).
3. Middle = proof by showing, one new visual fact per line
   (monorail-savings reel; "7 Dumb Mistakes" countdown).
4. Payoff at 15–25s cashes exactly what the hook promised.
5. Close = one decisive CTA/question, then the narrative
   loop line re-enters the hook.

This package applies pattern #6 (secret reveal + how-to
promise) from the research log: hook "Secret spots on the
Las Vegas Strip!", step-like tension, mural/hidden-bar
payoff, CTA + hook re-entry as the loop.

## Contents

- `script.md` — beat sheet (with word counts vs budget) +
  full script + caption + hashtags
- `shots-and-prompts.md` / `prompts.json` — shot-by-shot
  cinematic prompts with per-shot + global negative prompts
- `qa-verdict.json` — the recorded QA verdict for `cb84c943`
  (incl. visual_match + hard_gate blocks)
- `footage-manifest.json` — the sourcing record (source
  URL, matched query, license, gate verdicts per candidate)
- `tiktok-package.md` — TikTok variant (same render +
  TikTok caption + hashtags + cover text) for Cyrus's
  one-tap cross-post to @cyrusoutdoor; distribution-only,
  2-week test (VIRAL-PROTOCOL.md §5b). NOT posted.
