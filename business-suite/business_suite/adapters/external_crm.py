"""External CRM adapter (HubSpot/Salesforce-style) — STUB.

The suite's source of truth is the local CRM store
(business_suite/crm.py). Syncing records outward to a client's own
CRM needs that CRM's API key (EXTERNAL_CRM_API_KEY) and a mapping of
fields agreed with the client. Until then, `push_record` refuses —
loudly — rather than claiming a sync that never happened.
"""

from __future__ import annotations

import os
from typing import Optional

from .base import NotConfiguredError


class ExternalCRMAdapter:
    """One-way push of local CRM records to an external CRM."""

    def __init__(self, client_id: str, provider: str = "hubspot"):
        self.client_id = client_id
        self.provider = provider

    def _missing_reason(self) -> Optional[str]:
        if not os.environ.get("EXTERNAL_CRM_API_KEY"):
            return ("missing environment variable: EXTERNAL_CRM_API_KEY "
                    f"(the client's own {self.provider} key, set at deployment)")
        return (f"credentials are present, but the {self.provider} sync "
                "mapping is not implemented in this package version — it "
                "is built per client during onboarding")

    def status(self) -> dict:
        reason = self._missing_reason()
        return {
            "provider": self.provider,
            "client_id": self.client_id,
            "configured": reason is None,
            "reason": reason or "configured",
        }

    def push_record(self, kind: str, record: dict) -> dict:
        reason = self._missing_reason()
        if reason is not None:
            raise NotConfiguredError(f"external CRM push not configured: {reason}")
        raise NotConfiguredError(
            "external CRM reports configured but has no push implementation "
            "— refusing to pretend the record was synced."
        )
