"""WhatsApp Business adapter — STUB (honest by design).

Live sending needs the WhatsApp Business Platform (Meta) with the
CLIENT's own phone-number ID and access token, supplied at deployment
via the environment variables WHATSAPP_PHONE_NUMBER_ID and
WHATSAPP_ACCESS_TOKEN. This package ships no credentials and no live
send path, so the adapter reports exactly what is missing.
"""

from __future__ import annotations

import os
from typing import Optional

from .base import ChannelAdapter


class WhatsAppAdapter(ChannelAdapter):
    channel = "whatsapp"

    def _missing_reason(self) -> Optional[str]:
        missing = [name for name in ("WHATSAPP_PHONE_NUMBER_ID", "WHATSAPP_ACCESS_TOKEN")
                   if not os.environ.get(name)]
        if missing:
            return ("missing environment variables: " + ", ".join(missing) +
                    " (the client's own WhatsApp Business credentials, "
                    "set at deployment)")
        return ("credentials are present, but the live Meta Graph API send "
                "path is not implemented in this package version — wiring "
                "it is a deployment step, quoted per client")
