"""CYRUS TEAM — smart_agents/strategist_agent.py

🧠 THE MASTERMIND — strategist & market analyst (Senior).

Charter job: watch trends, analyse the market, design the content
calendar, and inject DATA-BASED video ideas into the team. He must
know what is actually moving — from real signals, never guesses.

What lives here (one agent, four real capabilities):
1. TREND SIGNALS — live DuckDuckGo web search (adapted from
   ultimate-robot-team `robots/trend_watcher.py`). Every signal
   records its source URL, query and fetch time, so any human can
   verify the grounding. HARD RULE (the rebuild fixes audit
   diagnosis #2 — the old factory's "trend_scout" asked an LLM for
   trends FROM MEMORY and called it data): this search is the ONLY
   source of trend signals. If it fails, the result is ok=False and
   NO signals — and then NO ideas.
2. VIRAL VIDEO IDEAS — hook-first generation (adapted from URT
   `robots/youtube_idea_robot.py`) grounded ONLY in collected
   signals, via the thinking tier. No signals or no AI => no
   ideas, honestly reported.
3. CONTENT CALENDAR — a JSON calendar this agent reads and writes
   (locked cadence: 1 strong post/day/platform, Cyrus's order).
4. ANALYTICS FEEDBACK — real outcome counts from the team's own
   queue; platform analytics feeds report "no data connected yet"
   until real credentials exist. Never an invented metric.

Two-state rule (Cyrus, 2026-10-27): every action either EXECUTES
for real, or reports «نمی‌شه» with the reason. Zero hallucination.
"""

import argparse
import html as html_module
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import uuid
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

from smart_agents import common  # noqa: E402
from smart_agents.queue import ApprovalQueue  # noqa: E402

log = common.get_logger("strategist")

# ==================================================================
# 1. TREND SIGNALS — real live search (URT robots/trend_watcher.py)
#
# Technical note (from the original): DuckDuckGo's plain GET
# endpoint serves a bot-challenge page on this network, but
# submitting the search as an HTML FORM (POST) returns real results.
# ==================================================================

_DDG = "https://html.duckduckgo.com/html/"
_UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"


def _search_once(query):
    form = urllib.parse.urlencode({"q": query}).encode("utf-8")
    req = urllib.request.Request(
        _DDG, data=form,
        headers={"User-Agent": _UA,
                 "Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        page = resp.read().decode("utf-8", errors="replace")
    trends = []
    for m in re.finditer(
            r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
            page, re.DOTALL):
        href, title_html = m.group(1), m.group(2)
        if "uddg=" in href:  # unwrap DuckDuckGo's redirect wrapper
            href = urllib.parse.unquote(
                href.split("uddg=", 1)[1].split("&")[0])
        title = html_module.unescape(
            re.sub(r"<[^>]+>", "", title_html).strip())
        if href.startswith("http") and title:
            trends.append({"title": title, "url": href})
    return trends


def watch(niche, max_results=5):
    """Search the live web for what's trending in a niche.

    Returns {"ok": True, "query": ..., "trends": [{"title","url"}]}
    or {"ok": False, "error": ...} when the search genuinely fails.
    Never raises, never invents a result.
    """
    query = f"{niche} trends social media"
    last_err = None
    # The egress path to DuckDuckGo is flaky (occasional bot-challenge
    # pages); retry with backoff and report honestly if all fail.
    for attempt in range(3):
        try:
            trends = _search_once(query)
            if trends:
                return {"ok": True, "query": query,
                        "trends": trends[:max_results]}
            last_err = "no results parsed (page layout or block)"
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
        time.sleep(1 * (2 ** attempt))
    log.warning("trend watch failed for %r: %s", niche, last_err)
    return {"ok": False, "query": query, "trends": [], "error": last_err}


def collect_signals(topics, max_per_topic=5):
    """Collect trend signals for a list of topics.

    Returns {"ok": bool, "signals": [...], "failures": [...],
             "fetched_at": iso timestamp}.
    Each signal: {"topic", "title", "url", "query", "fetched_at"}.
    "ok" is True only when at least one topic produced real
    results. A failed topic lands in "failures" with its real
    error — it contributes NO signals.
    """
    signals = []
    failures = []
    fetched_at = datetime.now().isoformat()
    for topic in topics or []:
        result = watch(topic, max_results=max_per_topic)
        if result.get("ok"):
            for t in result["trends"]:
                signals.append({
                    "topic": topic,
                    "title": t["title"],
                    "url": t["url"],
                    "query": result["query"],
                    "fetched_at": fetched_at,
                })
        else:
            failures.append({"topic": topic,
                             "error": result.get("error")})
    log.info("signals: %d collected, %d topic(s) failed",
             len(signals), len(failures))
    return {"ok": len(signals) > 0, "signals": signals,
            "failures": failures, "fetched_at": fetched_at}


# ==================================================================
# 2. VIRAL VIDEO IDEAS — hook-first, grounded in real signals only
# ==================================================================

_IDEA_SYSTEM = (
    "You are THE MASTERMIND — strategist of an AI travel content "
    "team (Cyrus AI: AI trip planning for Canada + USA, CA$10 for "
    "14 days). You design short-video ideas from REAL trend signals "
    "only — the signals are given to you with their source URLs. "
    "You never claim something is trending unless a signal says so. "
    "Every idea is HOOK-FIRST: the hook is the exact line shown in "
    "the first 2 seconds and must stop the scroll. "
    "VIRAL PROTOCOL (standing): every idea is designed for the "
    "30-second golden formula — 0-3s Hook, 3-15s Tension, "
    "15-25s Climax (payoff), 25-30s Loop & CTA — and must name "
    "its LOOP: how the final spoken line hands back into the "
    "hook line so an auto-replay feels seamless (a NARRATIVE "
    "loop for watch time; footage looping is forbidden and is "
    "never what 'loop' means here). The team's living formula "
    "file, when provided, is binding craft knowledge — follow "
    "its hook formulas and anti-patterns. Never invent "
    "prices, hours, phone numbers or facts about places. Reply with "
    "ONLY valid JSON."
)


_RESEARCH_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "research")
VIRAL_FORMULAS_PATH = os.path.join(_RESEARCH_DIR, "VIRAL-FORMULAS.md")


def load_viral_formulas(max_chars=3000):
    """Read the team's living viral-formula knowledge file
    (research/VIRAL-FORMULAS.md, VIRAL-PROTOCOL.md §1/§5).

    Returns its text (truncated to max_chars) or "" when the
    file does not exist yet — idea generation then proceeds on
    the protocol alone and says nothing it cannot ground.
    """
    try:
        with open(VIRAL_FORMULAS_PATH, "r", encoding="utf-8") as f:
            return f.read()[:max_chars]
    except OSError:
        return ""


def generate_ideas(signals, n=3, niche="travel"):
    """Generate up to `n` hook-first ideas grounded in `signals`
    (from collect_signals).

    Returns {"ok": True, "ideas": [...]} — or an honest
    {"ok": False, "ideas": [], "error": ...} when there are no
    signals or the AI is unavailable. Never fabricates.
    """
    signals = [s for s in (signals or []) if s.get("title")]
    if not signals:
        return {"ok": False, "ideas": [],
                "error": ("no real trend signals — refusing to "
                          "invent ideas (نمی‌شه: بدون سیگنال واقعی، "
                          "ایده ساخته نمی‌شود)")}
    signal_block = "\n".join(
        f"- [{s.get('topic', niche)}] {s['title']} ({s['url']})"
        for s in signals[:15])
    formulas = load_viral_formulas()
    formulas_block = (
        "\nTEAM VIRAL FORMULA FILE (living knowledge — apply its "
        "hook formulas, pacing and loop rules):\n" + formulas + "\n"
        if formulas else "")
    prompt = (
        f"REAL trend signals collected just now from the live web:\n"
        f"{signal_block}\n"
        f"{formulas_block}\n"
        f"Design {n} short-video ideas for the {niche} niche, each "
        "grounded in at least one signal above. For each idea give:\n"
        "- hook: the exact first-2-seconds on-screen line\n"
        "- title: a short, honest title\n"
        "- angle: one sentence — what the video shows/decides\n"
        "- loop: how the final line hands back into the hook "
        "(narrative seamless loop per the Viral Protocol)\n"
        "- source_urls: the signal URL(s) it is grounded in\n"
        'Reply ONLY valid JSON: {"ideas": [{"hook": "...", '
        '"title": "...", "angle": "...", "loop": "...", '
        '"source_urls": ["..."]}]}'
    )
    data, ok = common.ask_json(prompt, _IDEA_SYSTEM, role="thinking",
                               max_tokens=900, temperature=0.6)
    if not ok or not data:
        return {"ok": False, "ideas": [],
                "error": ("AI unavailable (no key / no network / bad "
                          "response) — no ideas produced, none faked")}
    ideas = []
    signal_urls = {s["url"] for s in signals}
    for raw in (data.get("ideas") or [])[:n]:
        if not isinstance(raw, dict):
            continue
        hook = str(raw.get("hook", "")).strip()
        title = str(raw.get("title", "")).strip()
        if not hook or not title:
            continue
        urls = [u for u in (raw.get("source_urls") or [])
                if u in signal_urls]
        ideas.append({
            "hook": hook,
            "title": title,
            "angle": str(raw.get("angle", "")).strip(),
            "loop": str(raw.get("loop", "")).strip(),
            "topic": niche,
            "source_urls": urls,
        })
    if not ideas:
        return {"ok": False, "ideas": [],
                "error": "AI returned no usable ideas — none faked"}
    log.info("ideas: %d generated from %d signals", len(ideas),
             len(signals))
    return {"ok": True, "ideas": ideas}


# ==================================================================
# 3. CONTENT CALENDAR — JSON, read/write, locked cadence
# ==================================================================

# Locked cadence (Cyrus's standing order): 1 post/day/platform.
PLATFORMS = ("youtube", "instagram", "whatsapp", "telegram",
             "facebook")
POSTS_PER_DAY_PER_PLATFORM = 1

_HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CALENDAR_PATH = os.path.join(_HERE, "content_calendar.json")


class ContentCalendar:
    """A JSON content calendar with atomic saves (queue pattern).

    Slot: {"id", "date", "platform", "topic", "notes",
           "status": "planned"|"filled", "package_id"}.
    The calendar plans and records — it never invents performance
    data.
    """

    def __init__(self, path=None):
        self.path = os.path.abspath(path or DEFAULT_CALENDAR_PATH)
        self.slots = []
        self._load()

    def _load(self):
        try:
            if os.path.isfile(self.path):
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    self.slots = data
        except Exception as exc:
            log.warning("calendar load failed (%s) — starting empty",
                        exc)
            self.slots = []

    def _save(self):
        directory = os.path.dirname(self.path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.slots, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    def add_slot(self, slot_date, platform, topic, notes=""):
        """Add one planned slot. Returns the slot dict."""
        slot = {
            "id": f"{slot_date}-{platform}-{uuid.uuid4().hex[:4]}",
            "date": str(slot_date),
            "platform": platform,
            "topic": topic,
            "notes": notes,
            "status": "planned",
            "package_id": None,
        }
        self.slots.append(slot)
        self._save()
        return slot

    def plan_days(self, start_date, topics, days=7,
                  platforms=PLATFORMS):
        """Plan `days` days of slots from start_date ('YYYY-MM-DD'
        or datetime.date), cycling `topics` across platform slots.
        Pure data work — no AI. Raises ValueError on empty topics
        (refusing to plan empty content). Returns created slots."""
        if isinstance(start_date, str):
            y, m, d = (int(x) for x in start_date.split("-"))
            start = date(y, m, d)
        else:
            start = start_date
        topics = list(topics or [])
        if not topics:
            raise ValueError("plan_days needs at least one topic — "
                             "refusing to plan empty content")
        created = []
        ti = 0
        for offset in range(days):
            day = start + timedelta(days=offset)
            for platform in platforms:
                for _ in range(POSTS_PER_DAY_PER_PLATFORM):
                    topic = topics[ti % len(topics)]
                    ti += 1
                    created.append(self.add_slot(
                        day.isoformat(), platform, topic))
        log.info("calendar: planned %d slots from %s",
                 len(created), start.isoformat())
        return created

    def mark_filled(self, slot_id, package_id):
        """Mark a slot filled by a queue package. Returns bool."""
        for slot in self.slots:
            if slot.get("id") == slot_id:
                slot["status"] = "filled"
                slot["package_id"] = package_id
                self._save()
                return True
        return False

    def slots_for(self, slot_date):
        return [s for s in self.slots
                if s.get("date") == str(slot_date)]

    def upcoming(self, days=7, from_date=None):
        """Planned (unfilled) slots in the next `days` days."""
        start = from_date or date.today()
        if isinstance(start, str):
            y, m, d = (int(x) for x in start.split("-"))
            start = date(y, m, d)
        end = start + timedelta(days=days)
        out = [s for s in self.slots
               if s.get("status") == "planned"
               and start.isoformat() <= s.get("date", "") <=
               end.isoformat()]
        return sorted(out, key=lambda s: (s.get("date", ""),
                                          s.get("platform", "")))

    def all(self):
        return list(self.slots)


# ==================================================================
# 4. ANALYTICS FEEDBACK — real local numbers, honest gaps
# ==================================================================

def queue_outcomes(queue_path=None):
    """Real outcome counts from the team's own approval queue."""
    queue = ApprovalQueue(queue_path) if queue_path else ApprovalQueue()
    counts = {}
    for entry in queue.all():
        status = entry.get("status", "?")
        counts[status] = counts.get(status, 0) + 1
    return {"source": "approval_queue (local, real)",
            "total": len(queue.all()), "by_status": counts}


def platform_sources():
    """Which platform analytics feeds are actually connected —
    checked from credential presence only; no values are read
    into any report."""
    return [
        {"source": "youtube_data_api",
         "connected": bool(os.environ.get("YOUTUBE_CLIENT_SECRETS")),
         "reason": ("" if os.environ.get("YOUTUBE_CLIENT_SECRETS")
                    else "no YouTube OAuth credentials configured yet")},
        {"source": "instagram_insights",
         "connected": bool(os.environ.get("IG_ACCESS_TOKEN")),
         "reason": ("" if os.environ.get("IG_ACCESS_TOKEN")
                    else "no IG_ACCESS_TOKEN configured for this team")},
        {"source": "telegram_analytics",
         "connected": False,
         "reason": "no channel-analytics access configured"},
        {"source": "whatsapp_analytics",
         "connected": False,
         "reason": "no WhatsApp Business API configured"},
    ]


def analytics_feedback(queue_path=None):
    """The Mastermind's performance feedback bundle. When no
    platform feed is connected, the message says exactly that —
    idea scoring must not pretend to use data it lacks."""
    sources = platform_sources()
    connected = [s["source"] for s in sources if s["connected"]]
    if connected:
        message = ("platform analytics connected: "
                   + ", ".join(connected))
    else:
        message = ("no platform analytics data connected yet — "
                   "only the team's own queue outcomes are real. "
                   "Idea selection must rely on live trend signals, "
                   "not on performance numbers we do not have.")
    return {"ok": True,
            "queue_outcomes": queue_outcomes(queue_path),
            "platform_sources": sources,
            "connected_platforms": connected,
            "message": message}


# ==================================================================
# Agent facade + CLI
# ==================================================================

class StrategistAgent:
    """The Mastermind as one callable agent."""

    def __init__(self, calendar_path=None, queue_path=None):
        self.calendar = ContentCalendar(calendar_path)
        self.queue_path = queue_path

    def run(self, topics, n_ideas=3, niche="travel"):
        """Full strategist pass: real signals -> grounded ideas.
        Any stage failing returns its honest failure — the run
        never fabricates the missing stage."""
        collected = collect_signals(topics)
        if not collected["ok"]:
            return {"ok": False, "stage": "signals",
                    "error": ("live trend search produced no "
                              "signals — no ideas will be invented"),
                    "failures": collected["failures"]}
        ideas = generate_ideas(collected["signals"], n=n_ideas,
                               niche=niche)
        if not ideas["ok"]:
            return {"ok": False, "stage": "ideas",
                    "error": ideas["error"],
                    "signals": collected["signals"]}
        return {"ok": True, "ideas": ideas["ideas"],
                "signals": collected["signals"],
                "fetched_at": collected["fetched_at"]}

    def feedback(self):
        return analytics_feedback(self.queue_path)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="The Mastermind — strategist agent")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_run = sub.add_parser("run", help="signals -> ideas for topics")
    p_run.add_argument("topics", nargs="+")
    p_run.add_argument("--ideas", type=int, default=3)
    sub.add_parser("feedback", help="honest analytics feedback")
    p_plan = sub.add_parser("plan", help="plan calendar days")
    p_plan.add_argument("topics", nargs="+")
    p_plan.add_argument("--days", type=int, default=7)
    p_plan.add_argument("--start", default=date.today().isoformat())
    args = parser.parse_args(argv)

    agent = StrategistAgent()
    if args.cmd == "run":
        result = agent.run(args.topics, n_ideas=args.ideas)
    elif args.cmd == "feedback":
        result = agent.feedback()
    else:
        created = agent.calendar.plan_days(args.start, args.topics,
                                           days=args.days)
        result = {"ok": True, "planned": len(created)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
