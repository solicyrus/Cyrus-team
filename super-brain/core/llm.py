"""SUPER BRAIN — minimal AI wrapper.

Gives the brain (and every subordinate robot through it) real thinking:
each decision first tries the LLM; on any failure (no key, network error,
bad response) it returns (None, False) and the brain falls back to its
rule-based logic. Never raises, never blocks the team.

The API key comes from the OPENAI_API_KEY environment variable
(see config.py) — it is NEVER stored in the repo (.env is gitignored).
Cost: gpt-4o-mini, ~200 tokens/decision (~$0.001).
"""
import json
from config import config

MODEL = "gpt-4o-mini"
MAX_TOKENS = 200

SYSTEM = (
    "You are the decision brain of a robot team. Given a task and system health, "
    "decide priority (1-10), action, and one-line reasoning IN PERSIAN. "
    'Reply with ONLY valid JSON, no other text: '
    '{"priority": 5, "action": "SCHEDULE_NORMAL", "reasoning": "..."}. '
    "Valid actions: IMMEDIATE_EXECUTION, SCHEDULE_HIGH, SCHEDULE_NORMAL, REDUCE_LOAD."
)

_VALID_ACTIONS = {
    "IMMEDIATE_EXECUTION", "SCHEDULE_HIGH", "SCHEDULE_NORMAL", "REDUCE_LOAD",
}


def _client():
    key = (config.OPENAI_API_KEY or "").strip()
    if not key:
        return None
    from openai import OpenAI
    return OpenAI(api_key=key, timeout=20)


def ask_decision(task: dict, health: dict):
    """Ask the AI for a decision.

    Returns (decision_dict, True) on success, (None, False) on any failure.
    decision_dict: {"priority": int 1-10, "action": str, "reasoning": str}
    """
    client = _client()
    if client is None:
        return None, False
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": json.dumps(
                    {"task": task, "system_health": health}, ensure_ascii=False)},
            ],
            max_tokens=MAX_TOKENS,
            temperature=0.3,
        )
        text = (resp.choices[0].message.content or "").strip()
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            return None, False
        data = json.loads(text[start:end + 1])
        priority = max(1, min(10, int(data.get("priority", 5))))
        action = str(data.get("action", "SCHEDULE_NORMAL"))
        if action not in _VALID_ACTIONS:
            action = "SCHEDULE_NORMAL"
        reasoning = str(data.get("reasoning", ""))
        return {"priority": priority, "action": action,
                "reasoning": reasoning}, True
    except Exception:
        return None, False
