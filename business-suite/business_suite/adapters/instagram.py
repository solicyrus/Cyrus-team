"""Instagram adapter — STUB (honest by design).

Live DM/posting needs the Meta Graph API with the CLIENT's own
Instagram professional account and a long-lived access token
(IG_USER_ID + IG_ACCESS_TOKEN), plus app review for messaging scopes.
None of that is bundled; the adapter reports what is missing instead
of pretending to post.
"""

from __future__ import annotations

import os
from typing import Optional

from .base import ChannelAdapter


class InstagramAdapter(ChannelAdapter):
    channel = "instagram"

    def _missing_reason(self) -> Optional[str]:
        missing = [name for name in ("IG_USER_ID", "IG_ACCESS_TOKEN")
                   if not os.environ.get(name)]
        if missing:
            return ("missing environment variables: " + ", ".join(missing) +
                    " (the client's own Instagram professional account, "
                    "connected at deployment)")
        return ("credentials are present, but the live Meta Graph API path "
                "is not implemented in this package version — wiring it "
                "is a deployment step, quoted per client")
