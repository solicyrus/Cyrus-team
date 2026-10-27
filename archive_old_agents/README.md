# Archive — the old cyrus-team experiments (archived 2026-10-27)

Everything that lived in this repository before the 2026-10-27
rebuild was moved here, byte for byte, before the originals were
deleted:

- `main/py` — the CrewAI demo sketch (2026-10-22): 3 agents under a
  comment claiming 40, a placeholder API key, never run as a
  product.
- `super-brain/` — the generic robot-orchestration framework
  (2026-10-22/23): FastAPI brain + robot manager whose core task
  execution was a simulation (asyncio.sleep → "success") until
  `robots/real_robots.py` patched in 5 real robots. Built for a
  tour/chef context; zero social-media function.
- `requirements.txt` — the demo's two unpinned dependencies.

Why archived, not deleted outright: Cyrus's law is honesty with
evidence — the audit of 2026-10-27 (kept with the manager) judged
these files on what they actually were, and this archive is the
proof. **No file here is imported or referenced by the new team.**
The new system lives in `smart_agents/` + `main_pipeline.py`.
