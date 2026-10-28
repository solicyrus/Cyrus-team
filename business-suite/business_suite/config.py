"""Client configuration and on-disk layout for the Business Suite.

White-label rule: ALL business-specific data lives under
`clients/<client-id>/`:

    config.json     — business name, niche, tone, contacts, services
    knowledge/      — .md / .txt files the Support Agent may quote
    inbox/          — email/form files the Workflow Agent processes
    data/crm.json   — created at runtime by the CRM store
    reports/        — created at runtime by the Workflow Agent

Onboarding a new client = copy the folder, edit config.json, drop in
knowledge files. No code changes, ever.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import List, Optional


class ConfigError(RuntimeError):
    """Raised when a client folder is missing or malformed."""


@dataclass
class ClientConfig:
    client_id: str
    business_name: str
    niche: str
    tone: str
    services: List[str] = field(default_factory=list)
    contact_email: str = ""
    contact_phone: str = ""
    website: str = ""
    channels: List[str] = field(default_factory=list)
    content_pillars: List[str] = field(default_factory=list)
    trend_seeds: List[str] = field(default_factory=list)
    hashtags: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, raw: dict) -> "ClientConfig":
        missing = [k for k in ("client_id", "business_name", "niche", "tone")
                   if not raw.get(k)]
        if missing:
            raise ConfigError(f"config.json is missing required fields: {missing}")
        contact = raw.get("contact", {})
        return cls(
            client_id=raw["client_id"],
            business_name=raw["business_name"],
            niche=raw["niche"],
            tone=raw["tone"],
            services=list(raw.get("services", [])),
            contact_email=contact.get("email", ""),
            contact_phone=contact.get("phone", ""),
            website=contact.get("website", ""),
            channels=list(raw.get("channels", [])),
            content_pillars=list(raw.get("content_pillars", [])),
            trend_seeds=list(raw.get("trend_seeds", [])),
            hashtags=list(raw.get("hashtags", [])),
        )


@dataclass
class ClientBundle:
    """A loaded client: config + every path an agent needs."""

    config: ClientConfig
    root: str  # clients/<client-id>/

    @property
    def knowledge_dir(self) -> str:
        return os.path.join(self.root, "knowledge")

    @property
    def inbox_dir(self) -> str:
        return os.path.join(self.root, "inbox")

    @property
    def data_dir(self) -> str:
        return os.path.join(self.root, "data")

    @property
    def crm_path(self) -> str:
        return os.path.join(self.data_dir, "crm.json")

    @property
    def reports_dir(self) -> str:
        return os.path.join(self.root, "reports")


def suite_root() -> str:
    """Absolute path of the business-suite/ folder."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_client(client_id: str, clients_dir: Optional[str] = None) -> ClientBundle:
    """Load one client folder, failing loudly if it is not there."""
    base = clients_dir or os.path.join(suite_root(), "clients")
    root = os.path.join(base, client_id)
    config_path = os.path.join(root, "config.json")
    if not os.path.isfile(config_path):
        raise ConfigError(f"No config.json for client '{client_id}' at {config_path}")
    with open(config_path, encoding="utf-8") as fh:
        raw = json.load(fh)
    config = ClientConfig.from_dict(raw)
    if config.client_id != client_id:
        raise ConfigError(
            f"Folder '{client_id}' holds config for '{config.client_id}' — "
            "folder name and client_id must match."
        )
    return ClientBundle(config=config, root=root)


def load_prompt(name: str) -> str:
    """Load a system-prompt file from business-suite/prompts/."""
    path = os.path.join(suite_root(), "prompts", name)
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def render_prompt(template: str, **values) -> str:
    """Fill {placeholder} slots by plain replacement.

    Deliberately NOT str.format: prompt files legitimately contain
    literal braces (JSON examples), which format() would choke on.
    Unknown placeholders are left untouched.
    """
    out = template
    for key, value in values.items():
        out = out.replace("{" + key + "}", str(value))
    return out
