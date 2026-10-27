"""CYRUS TEAM — smart_agents/facts.py

The deterministic fact-scan: the team's honesty guard against
invented prices, opening hours and phone numbers.

Adapted from ultimate-robot-team `content_factory/fact_critic.py`
(the strongest QA component in the old team, in daily service).
The deterministic scanner below is carried over nearly verbatim;
the AI advisory layer is rewired to this repo's smart_agents.common
(thinking tier).

THE RULE (architectural decision, 2026-10-25, kept): the
DETERMINISTIC scan is the ONLY hard-fail authority. The AI layer is
WARNINGS ONLY — its complaints are reported in "warnings" for the
human approver but can never set "passed" to False. Why: the AI
layer kept false-flagging approved content; the deterministic scan
has never false-flagged, and it catches the real dangers —
invented prices, hours, phone numbers.

If the AI layer is unavailable, the deterministic scan alone
decides (which it does anyway) and ai_used says so honestly.
"""

import re

from smart_agents import common

# The ONLY product facts team content may state (from URT
# content_factory/common.py APPROVED_FACTS).
APPROVED_FACTS = (
    "APPROVED FACTS — the ONLY product facts that may be stated: "
    "Cyrus AI trip planning costs CA$10 for 14 days at "
    "victoriatourandadventure.com; the app 'Cyrus AI Tour Guide' is "
    "on Google Play. NEVER invent prices, opening hours, phone "
    "numbers, distances, ferry times or facts about places — keep "
    "place talk general, visual and emotional."
)

_MONEY = re.compile(r"(CA\$|US\$|\$|CAD|USD)\s?\d[\d.,]*", re.IGNORECASE)
_CLOCK = re.compile(r"\b\d{1,2}(:\d{2})?\s?(am|pm)\b", re.IGNORECASE)
_PHONE = re.compile(r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b")
_APPROVED_MONEY = {"ca$10", "ca$ 10"}
# The approved token, strictly: CA$10 with an optional ".00".
# (A bare startswith("ca$10") would also wave through CA$100 —
# an invented price — so the token must match in full.)
_APPROVED_TOKEN = re.compile(r"ca\$\s?10(?:\.0+)?")

# --- APPROVED-FACTS whitelist -------------------------------------
# Matches that fall inside an approved-fact phrase are the approved
# fact itself, not an invention, and are skipped by the scan.
_APPROVED_SPAN_RES = (
    re.compile(r"ca\$\s?10\s+for\s+14\s+days", re.IGNORECASE),
    re.compile(r"cyrus\s+ai\s+trip\s+planning\s+costs\s+ca\$\s?10",
               re.IGNORECASE),
    re.compile(r"victoriatourandadventure\.com", re.IGNORECASE),
    re.compile(r"cyrus\s+ai\s+tour\s+guide", re.IGNORECASE),
    re.compile(r"google\s+play", re.IGNORECASE),
)
# Normalised (lowercase, single-spaced) distinctive phrases for
# quote matching in _is_approved.
_APPROVED_NORM = (
    "ca$10 for 14 days",
    "ca$ 10 for 14 days",
    "cyrus ai trip planning costs ca$10",
    "victoriatourandadventure.com",
    "cyrus ai tour guide",
    "google play",
)


def _approved_spans(text):
    """Character spans of `text` covered by an approved-fact
    phrase (case-insensitive)."""
    spans = []
    for rx in _APPROVED_SPAN_RES:
        spans.extend(m.span() for m in rx.finditer(text))
    return spans


def _inside(spans, match):
    return any(a <= match.start() and match.end() <= b
               for a, b in spans)


def _norm(s):
    return re.sub(r"\s+", " ", str(s or "").lower()).strip()


def _is_approved(quote):
    """True when a quoted phrase IS (part of) an approved fact —
    e.g. the whole approved price line, or the bare "CA$10" token
    lifted from inside it."""
    q = _norm(quote).strip("'\"")
    if not q:
        return False
    if q in _APPROVED_MONEY:
        return True
    return any(p in q or (len(q) >= 6 and q in p)
               for p in _APPROVED_NORM)


def scan_texts(texts):
    """Deterministic flags over a {field: text} dict — the ONLY
    hard-fail authority. Matches that fall inside an approved-fact
    phrase are skipped; every other price / hour / phone-shaped
    token is caught, quoting the offending token.

    Returns a list of flag strings (empty = clean).
    """
    flags = []
    for field, text in (texts or {}).items():
        t = str(text or "")
        spans = _approved_spans(t)
        for m in _MONEY.finditer(t):
            if _inside(spans, m):
                continue
            token = re.sub(r"\s+", " ", m.group(0).strip().lower())
            token = token.rstrip(".")
            if (token not in _APPROVED_MONEY
                    and not _APPROVED_TOKEN.fullmatch(token)):
                flags.append(f"{field}: unapproved money amount "
                             f"'{m.group(0).strip()}'")
        for m in _CLOCK.finditer(t):
            if _inside(spans, m):
                continue
            flags.append(f"{field}: clock time '{m.group(0).strip()}' "
                         "looks like an invented hour/schedule")
        for m in _PHONE.finditer(t):
            if _inside(spans, m):
                continue
            flags.append(f"{field}: phone-number-shaped string "
                         f"'{m.group(0).strip()}'")
    return flags


_SYSTEM = (
    "You are the FACT CRITIC of a travel content team — the honesty "
    "guard. You hunt for any statement of fact that was not given: "
    "invented prices, hours, distances, dates, statistics, or "
    "'best/only/first in the world' claims about places. "
    + APPROVED_FACTS + " Reply with ONLY valid JSON, no other text."
)

_FIELDS = ("hook", "title", "caption", "description", "script")
_QUOTED = re.compile(r"['\"]([^'\"]{3,})['\"]")


def _quote_field(quote, texts):
    """Return the field whose text actually contains the quote
    (whitespace/case-insensitive), or None. Used only to annotate
    AI warnings — never to fail anything."""
    q = _norm(quote).strip("'\"")
    if len(q) < 3:
        return None
    for field, text in (texts or {}).items():
        if q in _norm(text):
            return field
    return None


def _ai_warnings(data, texts):
    """Turn the AI layer's complaints into WARNINGS — all of them,
    unconditionally. The AI layer is advisory only: nothing it says
    can hard-fail a package."""
    warnings = []
    for raw in data.get("flags", []) or []:
        field = quote = claim = ""
        if isinstance(raw, dict):
            field = str(raw.get("field", "")).strip().lower()
            quote = str(raw.get("quote", "")).strip()
            claim = str(raw.get("claim", "")
                        or raw.get("problem", "")).strip()
        else:
            text = str(raw).strip()
            if not text:
                continue
            head, _, rest = text.partition(":")
            if head.strip().lower() in _FIELDS:
                field, claim = head.strip().lower(), rest.strip()
            else:
                claim = text
            m = _QUOTED.search(text)
            if m:
                quote = m.group(1).strip()
        if not claim and not quote:
            continue
        found = _quote_field(quote, texts) if quote else None
        label = field if field in _FIELDS else (found or "general")
        note = ""
        if quote and found and _is_approved(quote):
            note = " — this is an approved fact"
        elif quote and not found:
            note = " — quote not found in any field (unverified)"
        warnings.append(
            f"fact critic AI warning ({label}): "
            + (f"'{quote}'" if quote else "")
            + (f" — {claim}" if claim else "")
            + note)
    if data.get("passed") is False:
        warnings.append("fact critic AI verdict: failed "
                        "(warning only — AI verdicts never block)")
    return warnings


def check_facts(texts, use_ai=True):
    """Full fact check over {field: text}.

    Returns {"ok": True, "passed": bool, "flags": [...],
             "warnings": [...], "ai_used": bool}.
    "flags" holds ONLY deterministic-scan hits; "passed" is True
    iff the scan found nothing. The AI layer (thinking tier) adds
    warnings when available; use_ai=False skips it entirely.
    """
    flags = scan_texts(texts)
    warnings = []
    joined = "\n".join(f"{k}: {v}" for k, v in (texts or {}).items()
                       if str(v or "").strip())
    ai_used = False
    if use_ai and joined:
        prompt = (
            "Check these draft texts for INVENTED facts (anything "
            "stated as fact that is not in the approved facts and "
            "is not a general visual/emotional description):\n"
            + joined[:3000] + "\n"
            "For EVERY problem you find you MUST give:\n"
            "- field: which field it is in (hook, title, caption, "
            "description or script);\n"
            "- quote: the EXACT offending phrase, copied word for "
            "word from that field;\n"
            "- claim: the invented fact that phrase asserts (a "
            "price, hour, phone number, distance, date or place "
            "fact that was not given).\n"
            "Quote precisely — your complaints are advisory notes "
            "for a human approver. General praise, emotions and "
            "visual descriptions are NOT facts.\n"
            'Reply ONLY valid JSON: {"passed": true, "flags": '
            '[{"field": "...", "quote": "...", "claim": "..."}, '
            "...]} — passed=false only if at least one quoted "
            "invented fact is present."
        )
        data, ok = common.ask_json(prompt, _SYSTEM, role="thinking",
                                   max_tokens=600, temperature=0.2)
        if ok and data is not None:
            ai_used = True
            warnings.extend(_ai_warnings(data, texts))
    return {"ok": True, "ai_used": ai_used,
            "passed": len(flags) == 0, "flags": flags,
            "warnings": warnings}
