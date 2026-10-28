"""Business Suite — white-label automation agents for client businesses.

Three agents, one codebase, per-client configuration:

- SupportAgent   — answers customers ONLY from the client's knowledge
                   files and captures leads into a local CRM store.
- ContentAgent   — trend scan, content calendar, short-video scripts,
                   captions and hashtags, tuned per client niche/tone.
- WorkflowAgent  — classifies an inbox of emails/forms, records orders
                   and appointments, and writes a daily summary report.

Honesty rules baked into the code:
- No invented facts: support answers are grounded in knowledge files,
  and the agent says so when the answer is not there.
- Every integration that is not real yet is an adapter stub that
  reports "not configured" — nothing fakes success.
- The LLM is an optional enhancer behind a thin wrapper. Without a
  key, agents run in a deterministic mode and SAY so in their output.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
