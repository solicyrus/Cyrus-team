# -*- coding: utf-8 -*-
"""CYRUS TEAM — smart_agents/channels.py

Team channel registry — the one place every agent reads our
channels from. Reused from ultimate-robot-team `brain/channels.py`
(registered by Cyrus's order, 2026-10-25). Update links HERE only.
"""

CHANNELS = {
    "youtube": {
        "name": "Cyrus AI",
        "handle": "@CyrusAIGuide",
        "url": "https://www.youtube.com/@CyrusAIGuide",
    },
    "facebook": {
        "name": "Cyrus Outdoors",
        "url": "https://www.facebook.com/cyrus.soli",
    },
    "whatsapp": {
        "name": "Cyrus Team",
        "url": "https://whatsapp.com/channel/0029VbDkc9g6WaKg0owHJE3B",
    },
    "telegram": {
        "name": "Cyrus Team Bot",
        "handle": "@Cyrus_team_bot",
        "url": "https://t.me/Cyrus_team_bot",
    },
    "telegram_channel": {
        "name": "Cyrus AI",
        "handle": "@CyrusAIGuide",
        "url": "https://t.me/CyrusAIGuide",
    },
    "website": {
        "name": "Victoria Tour and Adventure",
        "url": "https://victoriatourandadventure.com",
    },
    "app": {
        "name": "Cyrus AI Tour Guide (Google Play)",
        "url": "https://play.google.com/store/apps/details?id=com.victoriatourandadventure.app",
    },
}


def channels_text():
    """One-line-per-channel summary for prompts."""
    lines = []
    for key, ch in CHANNELS.items():
        lines.append(f"- {key}: {ch['name']} — {ch['url']}")
    return "\n".join(lines)
