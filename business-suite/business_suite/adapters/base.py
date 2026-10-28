"""Base contract for channel/CRM adapters."""

from __future__ import annotations

from typing import Optional


class NotConfiguredError(RuntimeError):
    """Raised when an integration cannot honestly perform.

    The message always says WHAT is missing, so a deployment engineer
    (or the client) knows the exact next step.
    """


class ChannelAdapter:
    """Common shape for messaging-channel adapters.

    Subclasses set `channel` and implement `_missing_reason()`.
    Until a subclass grows a real, credential-backed implementation,
    `send_message` raises NotConfiguredError — by design.
    """

    channel = "unknown"

    def __init__(self, client_id: str, settings: Optional[dict] = None):
        self.client_id = client_id
        self.settings = settings or {}

    def _missing_reason(self) -> Optional[str]:
        """Return None if fully configured, else why it is not."""
        return "no implementation is bundled with this package version"

    def status(self) -> dict:
        """Honest, machine-readable configuration status."""
        reason = self._missing_reason()
        return {
            "channel": self.channel,
            "client_id": self.client_id,
            "configured": reason is None,
            "reason": reason or "configured",
        }

    def send_message(self, to: str, text: str) -> dict:
        reason = self._missing_reason()
        if reason is not None:
            raise NotConfiguredError(f"{self.channel} adapter not configured: {reason}")
        # Reaching here requires a subclass that really sends and has
        # overridden send_message; the base class itself never fakes it.
        raise NotConfiguredError(
            f"{self.channel} adapter reports configured but has no send "
            "implementation — refusing to pretend the message was sent."
        )
