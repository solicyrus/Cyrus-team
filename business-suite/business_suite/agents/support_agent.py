"""Support Agent — grounded customer answers + lead capture.

Grounding contract (the product's core promise):
- An answer is composed ONLY from knowledge sections retrieved for
  the question. If no section matches, the agent refuses honestly,
  in the brand's voice, and points the customer at a human.
- With an LLM configured, the model may REPHRASE the retrieved
  passages (the prompt forbids adding facts). Without one, the agent
  composes the answer deterministically from the passages themselves.
  Either way, `AnswerResult.mode` says which happened — never hidden.

Lead capture is explicit and inspectable: contact details found in a
customer message (or passed in directly) become CRM records.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

from .. import knowledge as kb
from ..config import ClientBundle, load_prompt, render_prompt
from ..crm import CRMStore
from ..llm import LLMCallError, LLMClient, LLMNotConfigured

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}")


@dataclass
class AnswerResult:
    answer: str
    grounded: bool                       # True iff built from knowledge
    sources: List[str] = field(default_factory=list)   # section labels
    mode: str = "deterministic"          # "llm" | "deterministic"
    lead: Optional[dict] = None          # CRM record, if one was captured


class SupportAgent:
    def __init__(self, client: ClientBundle, llm: Optional[LLMClient] = None,
                 crm: Optional[CRMStore] = None):
        self.client = client
        self.cfg = client.config
        self.llm = llm
        self.crm = crm or CRMStore(client.crm_path)
        self.sections = kb.load_knowledge(client.knowledge_dir)
        self._system_prompt = load_prompt("support_agent.md")

    # -- answering -----------------------------------------------------

    def answer(self, question: str) -> AnswerResult:
        """Answer one customer question, grounded or honestly refused."""
        hits = kb.search(question, self.sections)
        if not hits:
            return AnswerResult(
                answer=self._refusal(),
                grounded=False,
                sources=[],
                mode="deterministic",
            )
        passages = [section for section, _ in hits]
        answer_text, mode = self._compose(question, passages)
        return AnswerResult(
            answer=answer_text,
            grounded=True,
            sources=[s.label for s in passages],
            mode=mode,
        )

    def _refusal(self) -> str:
        cfg = self.cfg
        contact_bits = [b for b in (cfg.contact_email, cfg.contact_phone) if b]
        contact_line = " or ".join(contact_bits) if contact_bits else "our front desk"
        return (
            f"Thanks for asking — I don't have that information in front of me, "
            f"and I'd rather not guess. Please reach us at {contact_line} and a "
            f"person from {cfg.business_name} will help you directly."
        )

    def _compose(self, question: str, passages) -> tuple:
        """Build the answer text; returns (text, mode)."""
        if self.llm is not None:
            try:
                system = render_prompt(
                    self._system_prompt,
                    business_name=self.cfg.business_name,
                    niche=self.cfg.niche,
                    tone=self.cfg.tone,
                    contact_email=self.cfg.contact_email or "(not provided)",
                    contact_phone=self.cfg.contact_phone or "(not provided)",
                )
                joined = "\n\n".join(
                    f"[{s.label}]\n{s.text}" for s in passages)
                reply = self.llm.complete(
                    system,
                    f"KNOWLEDGE PASSAGES:\n{joined}\n\nCUSTOMER QUESTION: {question}",
                )
                if reply and reply.strip():
                    return reply.strip(), "llm"
            except (LLMNotConfigured, LLMCallError):
                pass  # fall through to deterministic composition, labelled
        return self._deterministic_answer(passages), "deterministic"

    @staticmethod
    def _deterministic_answer(passages) -> str:
        """Compose from the passages verbatim — facts cannot drift."""
        lines: List[str] = []
        for section in passages:
            body = "\n".join(
                ln for ln in section.text.splitlines()
                if not ln.lstrip().startswith("#")
            ).strip()
            if body:
                lines.append(body)
        return "\n\n".join(lines)

    # -- lead capture ----------------------------------------------------

    @staticmethod
    def extract_contact(text: str) -> Optional[str]:
        """First email or phone number in a message, else None."""
        match = _EMAIL_RE.search(text) or _PHONE_RE.search(text)
        return match.group(0) if match else None

    def capture_lead(self, *, name: str = "", contact: str = "",
                     need: str = "", channel: str = "website-chat") -> dict:
        """Record a lead in the CRM store. Contact or need is required —
        an empty lead is refused rather than stored as noise."""
        if not contact and not need:
            raise ValueError("A lead needs at least a contact or a stated need.")
        return self.crm.add_lead(name=name, contact=contact, need=need,
                                 channel=channel)

    def handle_message(self, text: str, *, name: str = "",
                       channel: str = "website-chat") -> AnswerResult:
        """Full inbound-message flow: capture a lead if the message
        carries contact details, then answer its question (if any)."""
        result = self.answer(text)
        contact = self.extract_contact(text)
        if contact:
            result.lead = self.capture_lead(
                name=name, contact=contact, need=text.strip()[:280],
                channel=channel)
        return result
