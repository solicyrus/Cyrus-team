"""Workflow Agent — inbox triage, records, daily summary.

Reads plain-text messages from the client's inbox/ folder (headers
From/Subject/Date, blank line, body — the shape any mail export or
form-forward produces), then for each message:

1. Classifies it: order / appointment / question / spam.
   Deterministic keyword rules first — inspectable, no model needed.
   Only when the rules cannot reach a confident verdict is the LLM
   asked (through the wrapper), and its raw reply must be strict
   JSON. If neither path is confident, the message lands in
   "needs_review" — a human decides. Nothing is silently forced
   into a category.
2. Extracts fields (sender, contact, phone, service, quantity,
   date/time mentions) with plain regexes and the client's own
   service list.
3. Writes orders and appointments into the CRM store; collects
   questions and needs_review items as "needs human action".
4. Emits a daily summary report (Markdown) the owner can read in
   one minute.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional

from ..config import ClientBundle, load_prompt, render_prompt
from ..crm import CRMStore
from ..llm import LLMCallError, LLMClient, LLMNotConfigured

# -- classification rules -------------------------------------------------

_SPAM_PHRASES = [
    "crypto", "bitcoin", "lottery", "you have won", "seo services",
    "rank your website", "click here", "free money", "giveaway",
    "double your", "guaranteed income", "work from home opportunity",
]
_APPOINTMENT_WORDS = [
    "appointment", "book", "booking", "schedule", "reschedule",
    "consultation", "check-up booking", "move my", "cancel my",
]
_ORDER_WORDS = [
    "order", "buy", "purchase", "quantity", "qty", "ship", "delivery",
    "deliver",
]
_QUESTION_PATTERNS = [
    r"\bdo you\b", r"\bdoes\b", r"\bcan i\b", r"\bhow much\b",
    r"\binsurance\b", r"\bprice\b", r"\bcost\b",
]
_RULE_THRESHOLD = 2

_MONTHS = ("January|February|March|April|May|June|July|August|"
           "September|October|November|December")
_DATE_RES = [
    re.compile(rf"\b(?:{_MONTHS})\s+\d{{1,2}}(?:st|nd|rd|th)?\b"),
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
    re.compile(r"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b"),
]
_TIME_RE = re.compile(r"\b\d{1,2}:\d{2}\s*(?:am|pm)?\b|\b\d{1,2}\s*(?:am|pm)\b",
                      re.IGNORECASE)
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}")
_QTY_PATTERNS = [
    re.compile(r"(?:quantity|qty)[:\s]+(\d+)", re.IGNORECASE),
    re.compile(r"(\d+)\s+(?:[a-z]+\s+){0,2}?(?:kits?|items?|units?|boxes)\b",
               re.IGNORECASE),
    re.compile(r"(\d+)\s*x\b", re.IGNORECASE),
    re.compile(r"\bx\s*(\d+)\b", re.IGNORECASE),
]


@dataclass
class Message:
    filename: str
    sender_name: str
    sender_email: str
    subject: str
    body: str


@dataclass
class ProcessedItem:
    filename: str
    category: str            # order|appointment|question|spam|needs_review
    method: str              # rules|llm-fallback|unresolved
    sender: str = ""
    subject: str = ""
    record_id: Optional[str] = None
    detail: str = ""


@dataclass
class WorkflowReport:
    date: str
    total: int
    counts: Dict[str, int]
    items: List[ProcessedItem] = field(default_factory=list)
    needs_action: List[ProcessedItem] = field(default_factory=list)
    report_path: Optional[str] = None


def parse_message_file(path: str) -> Message:
    with open(path, encoding="utf-8") as fh:
        raw = fh.read()
    headers, _, body = raw.partition("\n\n")
    sender_name, sender_email, subject = "", "", ""
    for line in headers.splitlines():
        low = line.lower()
        if low.startswith("from:"):
            value = line.split(":", 1)[1].strip()
            match = _EMAIL_RE.search(value)
            if match:
                sender_email = match.group(0)
                sender_name = value.replace(match.group(0), "").strip("<> ").strip()
            else:
                sender_name = value
        elif low.startswith("subject:"):
            subject = line.split(":", 1)[1].strip()
    return Message(filename=os.path.basename(path), sender_name=sender_name,
                   sender_email=sender_email, subject=subject,
                   body=body.strip())


class WorkflowAgent:
    def __init__(self, client: ClientBundle, llm: Optional[LLMClient] = None,
                 crm: Optional[CRMStore] = None):
        self.client = client
        self.cfg = client.config
        self.llm = llm
        self.crm = crm or CRMStore(client.crm_path)
        self._system_prompt = load_prompt("workflow_agent.md")

    # -- classification -----------------------------------------------

    def classify(self, msg: Message) -> tuple:
        """Returns (category, method). Categories include
        'needs_review' when nothing is confident — by design."""
        text = f"{msg.subject}\n{msg.body}".lower()
        if any(phrase in text for phrase in _SPAM_PHRASES):
            return "spam", "rules"
        scores = {
            "appointment": sum(1 for w in _APPOINTMENT_WORDS if w in text),
            "order": sum(1 for w in _ORDER_WORDS if w in text),
            "question": sum(1 for p in _QUESTION_PATTERNS if re.search(p, text))
                        + (1 if "?" in text else 0),
        }
        best = max(scores, key=scores.get)
        top = scores[best]
        second = sorted(scores.values())[-2]
        if top >= _RULE_THRESHOLD and top > second:
            return best, "rules"
        category = self._llm_classify(msg)
        if category:
            return category, "llm-fallback"
        return "needs_review", "unresolved"

    def _llm_classify(self, msg: Message) -> Optional[str]:
        if self.llm is None:
            return None
        try:
            system = render_prompt(
                self._system_prompt,
                business_name=self.cfg.business_name, niche=self.cfg.niche)
            reply = self.llm.complete(
                system,
                "CATEGORY_JSON\n---\n"
                f"Subject: {msg.subject}\n\n{msg.body}",
                max_tokens=60,
            )
            parsed = json.loads(reply)
            category = parsed.get("category")
            if category in ("order", "appointment", "question", "spam"):
                return category
        except (LLMNotConfigured, LLMCallError, ValueError, AttributeError):
            pass
        return None

    # -- extraction ------------------------------------------------------

    def _service_match(self, text: str) -> str:
        """Best-matching configured service, scored by how many of its
        distinctive words appear — so 'my teeth shifted, I want an
        Invisalign consultation' matches Invisalign (2 hits), not
        Teeth whitening (1 hit)."""
        low = text.lower()
        best_service, best_score = "", 0
        for service in self.cfg.services:
            tokens = [t for t in re.findall(r"[a-z]+", service.lower())
                      if t not in ("dental", "and", "the", "for")]
            score = 0
            for token in tokens:
                variants = {token, token + "s", token.rstrip("s")}
                if any(re.search(rf"\b{re.escape(v)}\b", low) for v in variants):
                    score += 1
            if score > best_score:
                best_service, best_score = service, score
        return best_service

    @staticmethod
    def _first_match(patterns, text: str) -> str:
        for pattern in patterns:
            match = pattern.search(text)
            if match:
                return match.group(0)
        return ""

    def _extract(self, msg: Message) -> dict:
        text = f"{msg.subject}\n{msg.body}"
        phone = _PHONE_RE.search(msg.body)
        quantity = None
        for pattern in _QTY_PATTERNS:
            qty_match = pattern.search(text)
            if qty_match:
                quantity = int(qty_match.group(1))
                break
        return {
            "customer": msg.sender_name or msg.sender_email,
            "contact": msg.sender_email,
            "phone": phone.group(0) if phone else "",
            "service": self._service_match(text),
            "quantity": quantity,
            "date_text": self._first_match(_DATE_RES, text),
            "time_text": (m.group(0) if (m := _TIME_RE.search(text)) else ""),
        }

    # -- main flow ---------------------------------------------------------

    def process_inbox(self, *, today: Optional[date] = None,
                      write_report: bool = True) -> WorkflowReport:
        today = today or date.today()
        inbox = self.client.inbox_dir
        files = []
        if os.path.isdir(inbox):
            files = sorted(f for f in os.listdir(inbox)
                           if f.lower().endswith((".txt", ".md", ".eml")))
        counts = {"order": 0, "appointment": 0, "question": 0,
                  "spam": 0, "needs_review": 0}
        items: List[ProcessedItem] = []
        needs_action: List[ProcessedItem] = []

        for name in files:
            msg = parse_message_file(os.path.join(inbox, name))
            category, method = self.classify(msg)
            counts[category] += 1
            item = ProcessedItem(
                filename=name, category=category, method=method,
                sender=msg.sender_email or msg.sender_name, subject=msg.subject)
            if category == "order":
                fields = self._extract(msg)
                item_name = fields["service"] or "Unspecified item"
                if "kit" in msg.body.lower() and "kit" not in item_name.lower():
                    item_name += " kit"
                record = self.crm.add_order(
                    customer=fields["customer"], contact=fields["contact"],
                    item=item_name, quantity=fields["quantity"],
                    source=msg.filename)
                item.record_id = record["id"]
                item.detail = f"{item_name} x{fields['quantity'] or '?'}"
            elif category == "appointment":
                fields = self._extract(msg)
                record = self.crm.add_appointment(
                    customer=fields["customer"], contact=fields["contact"],
                    service=fields["service"] or "Unspecified service",
                    date_text=fields["date_text"], time_text=fields["time_text"],
                    source=msg.filename)
                item.record_id = record["id"]
                item.detail = (f"{record['service']} — "
                               f"{fields['date_text']} {fields['time_text']}".strip())
            elif category in ("question", "needs_review"):
                item.detail = ("Unclassified — a human must read this"
                               if category == "needs_review"
                               else "Customer question — a human should reply")
                needs_action.append(item)
            items.append(item)

        report = WorkflowReport(
            date=today.isoformat(), total=len(files), counts=counts,
            items=items, needs_action=needs_action)
        if write_report:
            report.report_path = self._write_report(report)
        return report

    def _write_report(self, report: WorkflowReport) -> str:
        os.makedirs(self.client.reports_dir, exist_ok=True)
        path = os.path.join(self.client.reports_dir,
                            f"daily-summary-{report.date}.md")
        c = report.counts
        lines = [
            f"# Daily operations summary — {self.cfg.business_name}",
            f"Date: {report.date}",
            "",
            f"Processed {report.total} inbox messages:",
            f"- Orders: {c['order']}",
            f"- Appointments: {c['appointment']}",
            f"- Questions: {c['question']}",
            f"- Spam (discarded): {c['spam']}",
            f"- Needs review (unclassified): {c['needs_review']}",
            "",
            "## Records created",
        ]
        for item in report.items:
            if item.record_id:
                lines.append(f"- [{item.record_id}] {item.category}: "
                             f"{item.detail} (from {item.sender}, {item.filename})")
        lines += ["", "## Needs human action"]
        if report.needs_action:
            for item in report.needs_action:
                lines.append(f"- {item.category}: \"{item.subject}\" — "
                             f"{item.sender} ({item.filename}) — {item.detail}")
        else:
            lines.append("- Nothing outstanding.")
        lines += ["", "## All messages"]
        for item in report.items:
            lines.append(f"- {item.filename}: {item.category} "
                         f"(via {item.method})")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        return path
