"""Local CRM store — one JSON file per client.

Deliberately simple and inspectable: a small business can open the
file and see every lead, order and appointment the agents recorded.
Records are append-only through this API, get sequential ids
(lead-0001, order-0001, appt-0001) and UTC timestamps. Writes are
atomic (temp file + rename) so a crash cannot corrupt the store.

Pushing these records into an external CRM (HubSpot etc.) is the job
of adapters/external_crm.py — which is an honest stub until a real
integration is configured for a paying client.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from typing import List, Optional

_KINDS = ("leads", "orders", "appointments")
_PREFIX = {"leads": "lead", "orders": "order", "appointments": "appt"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class CRMStore:
    def __init__(self, path: str):
        self.path = path
        self._data = self._load()

    def _load(self) -> dict:
        if os.path.isfile(self.path):
            with open(self.path, encoding="utf-8") as fh:
                data = json.load(fh)
            for kind in _KINDS:
                data.setdefault(kind, [])
            return data
        return {kind: [] for kind in _KINDS}

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(self.path), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(self._data, fh, indent=2, ensure_ascii=False)
            os.replace(tmp, self.path)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def _add(self, kind: str, record: dict) -> dict:
        seq = len(self._data[kind]) + 1
        record = {"id": f"{_PREFIX[kind]}-{seq:04d}", "created_at": _now_iso(), **record}
        self._data[kind].append(record)
        self._save()
        return record

    # -- public API ---------------------------------------------------

    def add_lead(self, *, name: str = "", contact: str = "", need: str = "",
                 channel: str = "") -> dict:
        return self._add("leads", {
            "name": name, "contact": contact, "need": need, "channel": channel,
        })

    def add_order(self, *, customer: str = "", contact: str = "", item: str = "",
                  quantity: Optional[int] = None, source: str = "") -> dict:
        return self._add("orders", {
            "customer": customer, "contact": contact, "item": item,
            "quantity": quantity, "source": source, "status": "new",
        })

    def add_appointment(self, *, customer: str = "", contact: str = "",
                        service: str = "", date_text: str = "",
                        time_text: str = "", source: str = "") -> dict:
        return self._add("appointments", {
            "customer": customer, "contact": contact, "service": service,
            "date_text": date_text, "time_text": time_text,
            "source": source, "status": "requested",
        })

    def list(self, kind: str) -> List[dict]:
        if kind not in _KINDS:
            raise ValueError(f"Unknown CRM kind: {kind!r} (expected one of {_KINDS})")
        return list(self._data[kind])

    def counts(self) -> dict:
        return {kind: len(self._data[kind]) for kind in _KINDS}
