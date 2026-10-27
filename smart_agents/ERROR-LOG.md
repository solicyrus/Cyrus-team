# ERROR LOG — smart_agents

Institutional memory of failures, gate STOPs and rejections
(Zero-Waste Protocol, Cyrus 2026-10-27). Every STOP or rejection
produced by the pre-render semantic check, the visual gate, the
footage-coverage rule or the QA hard gate is appended here by
the agents themselves (`common.append_error_log`). Nothing in
this log is deleted; fixes are recorded as new entries.

## Critical Failure #001 — 2026-10-27 — The Whale Video

- **Draft:** `77302239` — "Hidden Gems of the Las Vegas Strip"
  (status at the time: draft, approval gate — never published).
- **What happened:** Cyrus reviewed the video himself and
  rejected it on sight: the footage showed **orca whales
  swimming in nature** while the voice and captions talked
  about hidden bars and streets of Las Vegas — a complete
  visual-script mismatch in a package that had passed every
  existing QA gate.
- **Root cause (two failures, not one):**
  1. Footage selection was **topic-blind**: renders were filled
     from Cyrus's personal footage bank (Victoria / nature
     clips) with no relation to the script's topic or words.
  2. QA had **no eyes**: the gate read the script and probed
     the file's technical facts, but never looked at a single
     frame — so nothing in the system could catch a picture
     that contradicted the words.
- **The fix (Zero-Waste Protocol, locked the same day):**
  topic-matched stock sourcing driven by the script's own
  keywords; a FREE pre-render metadata gate that stops
  off-topic clips before any API/render spend; per-clip and
  per-render vision verification; a beat-synced render (voice
  beat boundaries = scene cuts); the QA hard gate Q1–Q4 as
  THE pass/fail gate; and this error log. Draft 77302239 was
  superseded by a regenerated package built from real Las
  Vegas footage.

## 2026-10-27T23:01:43 — [SMOKE TEST] Pre-render STOP (metadata gate)
topic 'Las Vegas Strip': 1 candidate clip(s) STOPPED by the free metadata gate with zero further spend (Zero-Waste Protocol)
stopped: Orca whales in the wild [wikimedia_commons] — STOP: metadata content class ['nature', 'wildlife', 'whales', 'orca', 'ocean'] contradicts the urban topic 'Las Vegas Strip' (Zero-Waste stop rule)

## 2026-10-27T23:01:43 — [SMOKE TEST] Footage STOP (coverage)
topic-matched footage covers only 0.0s of the 30s target for 'Las Vegas Strip' — package STOPPED instead of filling with off-topic clips
manifest: /tmp/smoke_footage/footage_manifest.json

## 2026-10-27T23:02:54 — Footage STOP (coverage)
topic-matched footage covers only 0.0s of the 30s target for 'hidden attractions on Las Vegas Strip' — package STOPPED instead of filling with off-topic clips
manifest: work/b5f69133/footage/footage_manifest.json

## 2026-10-27T23:05:08 — Footage STOP (coverage)
topic-matched footage covers only 22.074s of the 30s target for 'hidden spots on Las Vegas Strip' — package STOPPED instead of filling with off-topic clips
manifest: work/9f15fa69/footage/footage_manifest.json

## 2026-10-27T23:16:01 — Protocol update — Forever Protocol v2 adopted
Cyrus issued Forever Protocol v2, superseding the v1 zero-waste QA list
the four laws (visual-script alignment 100%, viral mechanics, real & cinematic quality, zero-waste QA gate) now govern all packages; the hard gate is FIVE questions (image<->text 100% with sync evidence recorded under Q1; hook thumb-stopping power; footage real/clear/no ugly effects; voice & sound clean — measured; closing verbal loop smooth); the v1 viral-4 checklist continues as advisory scoring; Law 3 native-resolution sharpness (crop factor <= 1.05) is enforced at stock selection in the developer. Implemented in qa_agent.py (hard_gate v2 + measure_audio) and developer_agent.py (resolution gate); consolidated in VIRAL-PROTOCOL.md §8.

## 2026-10-27T23:21:11 — Footage STOP (coverage)
topic-matched footage covers only 0.0s of the 30s target for 'hidden spots on Las Vegas Strip' — package STOPPED instead of filling with off-topic clips
manifest: work/39b70639/footage/footage_manifest.json

## 2026-10-27T23:30:15 — QA hard-gate rejection
package 25273f2c rejected by the hard gate (Forever Protocol v2)
reasons: viral checklist failed Q4 (Loop integrity): The final line 'Secret spots await!' does not directly re-enter the hook 'Secret spots on the Las Vegas Strip!' for seamless replay.; hard gate Q4 answered NO (Are the narrator voice and sound effects clean and cinematic?): peak -0.4 dB (clipping if > -0.5), mean -18.8 dB, longest mid-video silence 4.1s (limit 5.5s), speech in every beat: True

## 2026-10-27T23:34:17 — QA hard-gate rejection
package 960f5b0c rejected by the hard gate (Forever Protocol v2)
reasons: hard gate Q4 answered NO (Are the narrator voice and sound effects clean and cinematic?): peak -0.0 dB (clipping at 0 dBFS; fail if > -0.2), mean -19.5 dB, longest mid-video silence 4.04s (limit 5.5s), speech in every beat: True
