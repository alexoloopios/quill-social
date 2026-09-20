"""Fetch account updates without touching the UI or its SQLite connection."""
from __future__ import annotations

from dataclasses import dataclass, field

from quill_social.adapters.base import AdapterError
from quill_social.adapters.registry import adapter_for
from quill_social.model import SocialItem


@dataclass
class RefreshResult:
    items: list[SocialItem] = field(default_factory=list)
    posts: int = 0
    errors: list[str] = field(default_factory=list)


def fetch_accounts(accounts, credentials) -> RefreshResult:
    result = RefreshResult()
    for account in accounts:
        try:
            adapter = adapter_for(account, credentials)
            for item in adapter.home_timeline(limit=60):
                item.account_id = account.account_id
                result.items.append(item)
                result.posts += 1
            for item in adapter.notifications(limit=20):
                item.account_id = account.account_id
                result.items.append(item)
        except AdapterError as exc:
            result.errors.append(f"{account.label}: {exc}")
        except Exception as exc:
            result.errors.append(
                f"{account.label}: refresh failed ({type(exc).__name__}). "
                "Check the connection and account sign-in."
            )
    return result
