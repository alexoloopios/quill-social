"""Account-specific presentation and automatic announcement policy."""
import re
import unicodedata

WARNING_MODES = ("text_only", "warning_then_text", "warning_only")
SPEECH_SCOPES = ("home:all", "attention:mentions", "attention:notifications")


def sanitize_account_options(value):
    if not isinstance(value, dict):
        return {}
    result = {}
    for account, options in value.items():
        if not isinstance(account, str) or not isinstance(options, dict):
            continue
        mode = options.get("content_warning_mode", "warning_then_text")
        result[account] = {
            "content_warning_mode": mode if mode in WARNING_MODES else "warning_then_text",
            "speech_muted": options.get("speech_muted") is True,
            "sync_home_position": options.get("sync_home_position") is True,
            "speech_timelines": [scope for scope in SPEECH_SCOPES
                                 if scope in options.get("speech_timelines", [])]
            if isinstance(options.get("speech_timelines", []), list) else [],
        }
    return result


def plain_characters(text):
    # Explicit opt-in matching the recovered ASCII display filter. Stored text is intact.
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


def automatic_text(item, settings):
    options = settings.account_options.get(item.account_id, {})
    mode = options.get("content_warning_mode", "warning_then_text")
    text = item.text
    if item.content_warning:
        if mode == "warning_only":
            text = item.content_warning
        elif mode == "warning_then_text":
            text = item.content_warning + ". " + text
    if settings.exclude_web_addresses:
        text = re.sub(r"https?://\S+", "", text)
    if settings.notification_first_sentence:
        text = re.split(r"(?<=[.!?])\s+", text.strip(), maxsplit=1)[0]
    author = item.author_display or item.author_handle
    result = f"{author}: {text}"
    return plain_characters(result) if settings.remove_unicode else result
