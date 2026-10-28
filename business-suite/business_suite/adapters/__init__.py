"""Integration adapters.

Every adapter here follows one law: it either really does its job or
raises NotConfiguredError with the specific reason. There are no
placeholder sends, no "message queued" lies. Live channels get wired
per client, with that client's own credentials, at deployment time.
"""

from .base import ChannelAdapter, NotConfiguredError

__all__ = ["ChannelAdapter", "NotConfiguredError"]
