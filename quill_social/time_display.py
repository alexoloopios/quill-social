"""Presentation of epoch milliseconds; stored instants are never changed."""
from datetime import UTC, datetime


def display_datetime(ms: int, mode: str = "system") -> datetime:
    instant = datetime.fromtimestamp(ms / 1000, tz=UTC)
    # Convert each instant separately so historical daylight-saving rules apply.
    return instant if mode == "utc" else instant.astimezone()


def format_timestamp(ms: int | None, mode: str = "system", *, missing: str = "unknown") -> str:
    if ms is None:
        return missing
    return display_datetime(ms, mode).strftime("%Y-%m-%d %H:%M %Z")


def preference_for(parent) -> str:
    """Dialogs inherit the owning frame's presentation preference."""
    return getattr(getattr(parent, "a11y", None), "display_timezone", "system")
