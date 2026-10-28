"""Content Agent — trend scan, content calendar, scripts, captions.

Patterns adapted from the house social team (smart_agents), rebuilt
self-contained for client packaging: rotation calendars, hook-first
short scripts, one idea per video, filmable with a phone.

Honesty rules:
- Trend signals are labelled by source. Config seeds and the client's
  own service catalogue are real inputs; nothing here claims live
  market measurement. An LLM brainstorm, when configured, is labelled
  "llm" — a creative input, not data.
- Scripts are built by deterministic templates unless an LLM is
  configured AND returns valid structured output; `generated_with`
  on every result says which path produced it.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import List, Optional

from ..config import ClientBundle, load_prompt, render_prompt
from ..llm import LLMCallError, LLMClient, LLMNotConfigured

_WEEK_FORMATS = [
    "Short video (Reel/Short)",
    "Carousel",
    "Short video (Reel/Short)",
    "Story poll",
    "Short video (Reel/Short)",
    "Photo + caption",
    "Short video (Reel/Short)",
]

_DEFAULT_PILLARS = [
    "Education", "Myth vs fact", "How it works", "Meet the team",
    "Patient questions", "Seasonal offer", "Behind the scenes",
]

_HOOK_TEMPLATES = [
    "Nobody tells you this about {topic} — until now.",
    "Three things to know before your next {service} visit.",
    "Watch this before you book a {service}.",
    "The {topic} mistake we see every single week.",
    "You asked, we answer: {topic}, honestly.",
    "A quick look behind the scenes at {business}.",
    "Save this post — you'll want it before your next {service}.",
]


@dataclass
class TrendSignal:
    topic: str
    source: str          # "client-seed" | "service-catalogue" | "llm"
    note: str = ""


@dataclass
class CalendarItem:
    day: int
    date: str            # ISO date
    pillar: str
    format: str
    topic: str
    hook: str
    caption: str
    hashtags: List[str] = field(default_factory=list)


@dataclass
class Script:
    topic: str
    hook: str
    scenes: List[dict]   # {seconds, visual, spoken}
    cta: str
    caption: str
    hashtags: List[str] = field(default_factory=list)
    duration_s: int = 0
    generated_with: str = "deterministic"   # "llm" | "deterministic"


class ContentAgent:
    def __init__(self, client: ClientBundle, llm: Optional[LLMClient] = None):
        self.client = client
        self.cfg = client.config
        self.llm = llm
        self._system_prompt = load_prompt("content_agent.md")

    # -- trends ----------------------------------------------------------

    def trend_scan(self) -> List[TrendSignal]:
        signals = [
            TrendSignal(topic=seed, source="client-seed",
                        note="From the client's own trend seed list (config).")
            for seed in self.cfg.trend_seeds
        ]
        signals += [
            TrendSignal(topic=f"{service} — questions people ask first",
                        source="service-catalogue",
                        note="Derived from the client's configured services.")
            for service in self.cfg.services[:3]
        ]
        if self.llm is not None:
            signals += self._llm_trends()
        return signals

    def _llm_trends(self) -> List[TrendSignal]:
        try:
            reply = self.llm.complete(
                self._system(),
                "TASK: list 3 short-video content angles for this business. "
                "Reply with a JSON list of strings only.",
            )
            topics = json.loads(reply)
            if isinstance(topics, list):
                return [TrendSignal(topic=str(t), source="llm",
                                    note="LLM brainstorm — creative input, not market data.")
                        for t in topics if str(t).strip()]
        except (LLMNotConfigured, LLMCallError, ValueError):
            pass
        return []

    # -- calendar ----------------------------------------------------------

    def build_calendar(self, *, start: Optional[date] = None,
                       days: int = 7) -> List[CalendarItem]:
        start = start or date.today()
        pillars = self.cfg.content_pillars or _DEFAULT_PILLARS
        topics = self._topic_pool()
        items: List[CalendarItem] = []
        for i in range(days):
            pillar = pillars[i % len(pillars)]
            fmt = _WEEK_FORMATS[i % len(_WEEK_FORMATS)]
            topic = topics[i % len(topics)]
            hook = self._hook(i, topic)
            items.append(CalendarItem(
                day=i + 1,
                date=(start + timedelta(days=i)).isoformat(),
                pillar=pillar,
                format=fmt,
                topic=topic,
                hook=hook,
                caption=self._caption(hook, topic),
                hashtags=self._hashtags(pillar),
            ))
        return items

    def _topic_pool(self) -> List[str]:
        pool = list(self.cfg.services) + list(self.cfg.trend_seeds)
        return pool or [self.cfg.niche]

    def _hook(self, index: int, topic: str) -> str:
        template = _HOOK_TEMPLATES[index % len(_HOOK_TEMPLATES)]
        service = self.cfg.services[0] if self.cfg.services else self.cfg.niche
        return template.format(topic=topic.lower(), service=service.lower(),
                               business=self.cfg.business_name)

    def _caption(self, hook: str, topic: str) -> str:
        return (
            f"{hook} At {self.cfg.business_name} we keep "
            f"{self.cfg.niche} simple, honest and pressure-free. "
            f"Questions about {topic.lower()}? Send us a message — "
            f"a real person replies."
        )

    def _hashtags(self, pillar: str) -> List[str]:
        tags: List[str] = list(self.cfg.hashtags)
        words = [w for w in re.findall(r"[a-z]+", self.cfg.niche.lower())
                 if w not in ("and", "the", "for", "of")]
        if len(words) >= 2:
            field_word = words[-1].capitalize()
            for word in words[:-1]:
                tag = f"#{word.capitalize()}{field_word}"
                if tag not in tags:
                    tags.append(tag)
        pillar_tag = "#" + "".join(p.capitalize() for p in pillar.split())
        if pillar_tag not in tags:
            tags.append(pillar_tag)
        return tags[:10]

    # -- scripts -----------------------------------------------------------

    def write_script(self, item: CalendarItem) -> Script:
        if self.llm is not None:
            script = self._llm_script(item)
            if script is not None:
                return script
        return self._template_script(item)

    def _llm_script(self, item: CalendarItem) -> Optional[Script]:
        try:
            reply = self.llm.complete(
                self._system(),
                f"Write a 30-second short-video script.\n"
                f"TOPIC: {item.topic}\nPILLAR: {item.pillar}\nHOOK: {item.hook}\n"
                "Reply with JSON only: {\"hook\": str, \"scenes\": "
                "[{\"seconds\": str, \"visual\": str, \"spoken\": str}], "
                "\"cta\": str, \"caption\": str}",
            )
            raw = json.loads(reply)
            scenes = raw["scenes"]
            if not (raw.get("hook") and isinstance(scenes, list) and scenes
                    and raw.get("cta")):
                return None
            return Script(
                topic=item.topic,
                hook=str(raw["hook"]),
                scenes=[{"seconds": str(s.get("seconds", "")),
                         "visual": str(s.get("visual", "")),
                         "spoken": str(s.get("spoken", ""))} for s in scenes],
                cta=str(raw["cta"]),
                caption=str(raw.get("caption") or item.caption),
                hashtags=item.hashtags,
                duration_s=30,
                generated_with="llm",
            )
        except (LLMNotConfigured, LLMCallError, ValueError, KeyError, TypeError):
            return None

    def _template_script(self, item: CalendarItem) -> Script:
        service = self.cfg.services[0] if self.cfg.services else self.cfg.niche
        scenes = [
            {"seconds": "0-3", "visual": "Face to camera, clinic in background",
             "spoken": item.hook},
            {"seconds": "3-12", "visual": "Show the space / tools while talking",
             "spoken": f"Here is what {item.topic.lower()} actually involves at "
                       f"{self.cfg.business_name} — no surprises, no pressure."},
            {"seconds": "12-24", "visual": "Close-up of the process, step by step",
             "spoken": f"Most people ask about comfort and cost first. We walk you "
                       f"through both before any {service.lower()} begins."},
            {"seconds": "24-30", "visual": "Smile to camera, logo end card",
             "spoken": "Follow us for honest answers every week — and message us "
                       "your question for the next video."},
        ]
        return Script(
            topic=item.topic,
            hook=item.hook,
            scenes=scenes,
            cta="Follow + send your question by message",
            caption=item.caption,
            hashtags=item.hashtags,
            duration_s=30,
            generated_with="deterministic",
        )

    def _system(self) -> str:
        return render_prompt(
            self._system_prompt,
            business_name=self.cfg.business_name,
            niche=self.cfg.niche,
            tone=self.cfg.tone,
            hashtags=", ".join(self.cfg.hashtags),
        )
