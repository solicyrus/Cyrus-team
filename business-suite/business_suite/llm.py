"""Thin LLM wrapper for the Business Suite — the ONLY way agents talk
to a language model.

Design rules:
- The API key comes only from the OPENAI_API_KEY environment variable
  or a local `.env` file (repo root or business-suite folder). It is
  never printed, logged, stored in client configs, or committed.
- Standard library only (urllib), so the suite runs anywhere.
- Failure is explicit: no key -> LLMNotConfigured; API failure ->
  LLMCallError. Agents catch these and fall back to deterministic
  behaviour, labelling their output accordingly. Nothing silently
  pretends the model answered.
- Tests inject FakeLLM, a deterministic stand-in that honours the same
  interface, so the whole suite is provable with no network.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Callable, Optional, Protocol

DEFAULT_MODEL = "gpt-4o-mini"
_API_URL = "https://api.openai.com/v1/chat/completions"


class LLMNotConfigured(RuntimeError):
    """No API key available — the caller must not fake an answer."""


class LLMCallError(RuntimeError):
    """The API call itself failed (network, HTTP, bad response)."""


class LLMClient(Protocol):
    """Minimal interface every LLM backend (real or fake) honours."""

    def complete(self, system: str, user: str, *, max_tokens: int = 700) -> str:
        ...


def _parse_env_file(path: str) -> dict:
    values: dict = {}
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                values[key.strip()] = val.strip().strip('"').strip("'")
    except OSError:
        pass
    return values


def find_api_key() -> Optional[str]:
    """Locate OPENAI_API_KEY without ever exposing it.

    Search order: real environment, then `.env` next to the suite,
    then `.env` at the repo root (three levels above this file:
    business_suite/ -> business-suite/ -> repo root).
    """
    key = os.environ.get("OPENAI_API_KEY")
    if key:
        return key
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(os.path.dirname(here), ".env"),          # business-suite/.env
        os.path.join(os.path.dirname(os.path.dirname(here)), ".env"),  # repo root .env
    ]
    for path in candidates:
        key = _parse_env_file(path).get("OPENAI_API_KEY")
        if key:
            return key
    return None


class OpenAIClient:
    """Real client backed by the OpenAI chat-completions API."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self._api_key = api_key if api_key is not None else find_api_key()
        if not self._api_key:
            raise LLMNotConfigured(
                "OPENAI_API_KEY is not set (environment or .env); "
                "LLM features are unavailable, deterministic mode applies."
            )
        self.model = model or os.environ.get("BUSINESS_SUITE_MODEL", DEFAULT_MODEL)

    def complete(self, system: str, user: str, *, max_tokens: int = 700) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.4,
        }
        body = json.dumps(payload).encode("utf-8")
        last_error: Optional[Exception] = None
        for attempt in range(3):
            req = urllib.request.Request(
                _API_URL,
                data=body,
                method="POST",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"]
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code not in (429, 500, 502, 503, 504):
                    break  # non-transient: fail at once, honestly
            except (urllib.error.URLError, TimeoutError, KeyError, IndexError,
                    ValueError) as exc:
                last_error = exc
            if attempt < 2:
                time.sleep(2 if attempt == 0 else 5)
        raise LLMCallError(f"OpenAI call failed: {last_error}")


class FakeLLM:
    """Deterministic LLM stand-in for tests and offline demos.

    The handler receives (system, user) and must return the reply text.
    The default handler implements the small documented contracts the
    agents rely on:

    - Workflow fallback classification: if the prompt asks for a
      category and the message contains a question mark, it answers
      {"category": "question"} — a deliberately simple second opinion,
      different from the workflow agent's keyword rules.
    - Anything else: returns an empty string, which makes agents use
      their deterministic composition path (and label it as such).
    """

    def __init__(self, handler: Optional[Callable[[str, str], str]] = None):
        self._handler = handler or self._default_handler
        self.calls: list = []

    @staticmethod
    def _default_handler(system: str, user: str) -> str:
        if "CATEGORY_JSON" in user and "?" in user:
            return '{"category": "question"}'
        return ""

    def complete(self, system: str, user: str, *, max_tokens: int = 700) -> str:
        self.calls.append((system, user))
        return self._handler(system, user)


def get_llm() -> Optional[LLMClient]:
    """Return a real client when a key is available, else None.

    Agents treat None as "deterministic mode" and label output so.
    """
    try:
        return OpenAIClient()
    except LLMNotConfigured:
        return None
