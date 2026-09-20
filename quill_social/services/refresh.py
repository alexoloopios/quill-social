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
    home_positions: dict[str, str] = field(default_factory=dict)
    notification_keys: set[tuple[str, str]] = field(default_factory=set)


def fetch_accounts(accounts, credentials, *, limit: int = 60, sync_accounts=()) -> RefreshResult:
    result = RefreshResult()
    for account in accounts:
        try:
            adapter = adapter_for(account, credentials)
            for item in adapter.home_timeline(limit=limit):
                item.account_id = account.account_id
                result.items.append(item)
                result.posts += 1
            for item in adapter.notifications(limit=20):
                item.account_id = account.account_id
                result.items.append(item)
                result.notification_keys.add((item.account_id, item.remote_id))
            if account.account_id in sync_accounts and account.network == "mastodon":
                result.home_positions[account.account_id] = adapter.home_position()
        except AdapterError as exc:
            result.errors.append(f"{account.label}: {exc}")
        except Exception as exc:
            result.errors.append(
                f"{account.label}: refresh failed ({type(exc).__name__}). "
                "Check the connection and account sign-in."
            )
    return result
