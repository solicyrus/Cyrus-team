"""CYRUS TEAM — smart_agents/queue.py

The team's one approval queue: a JSON file with atomic saves.

Adapted from ultimate-robot-team `robots/runner.py`'s ApprovalQueue
— the proven queue the daily operation has run on since 2026-10-23
(extracted here without the runner's publishing/learning wiring,
which now lives in main_pipeline.py).

Statuses used by the pipeline:
    awaiting_qa       package built, waiting for the Strict QA gate
    rejected          QA refused it (qa_reasons recorded) — it can
                      NEVER be promoted to the publish queue from
                      this state by the pipeline
    draft             QA passed; the item sits in the publishing
                      queue as a DRAFT, held by the approval gate.
                      It is published ONLY when the AUTO_PUBLISH
                      environment flag is exactly "True" or a human
                      flips it to approved (standing rule: videos
                      are shown to Cyrus first). Queues written
                      before 2026-10-27 used the label
                      "awaiting_approval" for this same state; the
                      gate treats both labels identically.
    approved          manually approved; ready to publish
    published         every attempted channel reported a real send
    partial           some channels sent, some failed/skipped

The queue NEVER invents state: every status change is written to
disk immediately (tmp file + os.replace, so a crash cannot leave a
half-written queue).
"""

import json
import os

# Default location: approval_queue.json in the repo root. Callers
# (pipeline, proofs) may pass an explicit path — tests always do.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_PATH = os.path.join(PROJECT_ROOT, "approval_queue.json")

AWAITING_QA = "awaiting_qa"
REJECTED = "rejected"
DRAFT = "draft"
# Legacy label for the draft state (pre-2026-10-27 queues). The
# approval gate treats DRAFT and AWAITING_APPROVAL identically.
AWAITING_APPROVAL = "awaiting_approval"
APPROVED = "approved"
PUBLISHED = "published"
PARTIAL = "partial"


class ApprovalQueue:
    """approval_queue.json: content packages and their true state."""

    def __init__(self, path=None):
        self.path = os.path.abspath(path or DEFAULT_PATH)
        self.posts = []
        self._load()

    def _load(self):
        try:
            if os.path.isfile(self.path):
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    self.posts = data
        except Exception:
            self.posts = []

    def _save(self):
        # Atomic: write to a temp file, then replace.
        directory = os.path.dirname(self.path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.posts, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    def add(self, entry):
        self.posts.append(entry)
        self._save()
        return entry

    def find(self, post_id):
        """Exact id match, then unique-prefix match.
        Returns (entry, None) or (None, error_message)."""
        pid = (post_id or "").strip()
        if not pid:
            return None, "empty post id"
        exact = [p for p in self.posts if p.get("id") == pid]
        if exact:
            return exact[0], None
        pref = [p for p in self.posts
                if str(p.get("id", "")).startswith(pid)]
        if len(pref) == 1:
            return pref[0], None
        if len(pref) > 1:
            return None, f"ambiguous id {pid!r}: matches {len(pref)} posts"
        return None, f"unknown post id {pid!r}"

    def set_status(self, post_id, status, **extra):
        entry, err = self.find(post_id)
        if err:
            return False
        entry["status"] = status
        entry.update(extra)
        self._save()
        return True

    def by_status(self, status):
        return [p for p in self.posts if p.get("status") == status]

    def all(self):
        return list(self.posts)
