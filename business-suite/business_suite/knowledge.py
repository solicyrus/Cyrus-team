"""Knowledge loading and retrieval for the Support Agent.

The agent may ONLY answer from these files. Retrieval is plain,
inspectable keyword scoring — no embeddings, no magic — so a client
can always see exactly why a passage was (or was not) used.

Markdown files are split by heading; plain-text files by paragraph.
Each section keeps its source label ("pricing.md › Teeth whitening")
so answers can cite where a fact came from.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import List, Tuple

_STOPWORDS = {
    "a", "an", "the", "is", "are", "do", "does", "did", "you", "your",
    "we", "our", "i", "me", "my", "to", "of", "for", "in", "on", "at",
    "and", "or", "if", "it", "this", "that", "with", "can", "could",
    "please", "what", "when", "where", "which", "who", "how", "much",
    "many", "any", "have", "has", "will", "would", "there", "their",
}

# Small, deliberate synonym map so "cost" finds "price" without
# pretending to be a search engine. Extend per deployment if needed.
_SYNONYMS = {
    "cost": ["price", "fee", "charge"],
    "price": ["cost", "fee", "charge"],
    "open": ["hours", "opening"],
    "hours": ["open", "opening", "close", "closing"],
    "book": ["appointment", "booking"],
    "appointment": ["book", "booking", "visit"],
    "location": ["address", "located", "directions"],
    "address": ["location", "located"],
    "pay": ["payment", "billing", "insurance"],
    "payment": ["pay", "billing"],
    "insurance": ["billing", "coverage", "direct"],
    "park": ["parking"],
    "parking": ["park"],
}


def _words(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def content_words(text: str) -> List[str]:
    """Distinct meaningful words of a text, order preserved."""
    seen: List[str] = []
    for word in _words(text):
        if word not in _STOPWORDS and word not in seen:
            seen.append(word)
    return seen


def expand_terms(words: List[str]) -> List[str]:
    """Question words plus their known synonyms (question side only)."""
    out = list(words)
    for word in words:
        for syn in _SYNONYMS.get(word, []):
            if syn not in out:
                out.append(syn)
    return out


@dataclass
class KnowledgeSection:
    source_file: str
    heading: str
    text: str

    @property
    def label(self) -> str:
        return f"{self.source_file} › {self.heading}" if self.heading else self.source_file


def _split_markdown(filename: str, raw: str) -> List[KnowledgeSection]:
    sections: List[KnowledgeSection] = []
    heading = ""
    buf: List[str] = []

    def flush() -> None:
        text = "\n".join(buf).strip()
        if text:
            sections.append(KnowledgeSection(filename, heading, text))

    for line in raw.splitlines():
        match = re.match(r"^#{1,4}\s+(.*)$", line)
        if match:
            flush()
            heading = match.group(1).strip()
            buf = [line]
        else:
            buf.append(line)
    flush()
    return sections


def _split_text(filename: str, raw: str) -> List[KnowledgeSection]:
    sections = []
    for para in re.split(r"\n\s*\n", raw):
        para = para.strip()
        if para:
            first = para.splitlines()[0].strip().lstrip("# ").strip()
            sections.append(KnowledgeSection(filename, first[:60], para))
    return sections


def load_knowledge(knowledge_dir: str) -> List[KnowledgeSection]:
    """Load every .md/.txt knowledge file in a client folder."""
    sections: List[KnowledgeSection] = []
    if not os.path.isdir(knowledge_dir):
        return sections
    for name in sorted(os.listdir(knowledge_dir)):
        if not name.lower().endswith((".md", ".txt")):
            continue
        with open(os.path.join(knowledge_dir, name), encoding="utf-8") as fh:
            raw = fh.read()
        if name.lower().endswith(".md"):
            sections.extend(_split_markdown(name, raw))
        else:
            sections.extend(_split_text(name, raw))
    return sections


def search(
    question: str,
    sections: List[KnowledgeSection],
    *,
    limit: int = 2,
    min_matches: int = 2,
) -> List[Tuple[KnowledgeSection, int]]:
    """Score sections against a question.

    Returns [(section, matched_term_count)] sorted by score, keeping
    only sections matching at least `min_matches` distinct question
    terms (after synonym expansion). An empty result is meaningful:
    the caller must treat the question as out-of-knowledge.
    """
    terms = expand_terms(content_words(question))
    if not terms:
        return []
    scored: List[Tuple[KnowledgeSection, int]] = []
    for section in sections:
        body_hits = sum(1 for term in terms
                        if term in set(_words(section.text)))
        heading_hits = sum(1 for term in terms
                           if term in set(_words(section.heading)))
        # A section whose HEADING matches the question is almost
        # always the intended source ("Teeth whitening price" for a
        # price question), so heading hits count double.
        if body_hits + heading_hits >= min_matches:
            scored.append((section, body_hits + 2 * heading_hits))
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[:limit]
