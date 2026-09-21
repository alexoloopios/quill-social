from unittest.mock import Mock

import pytest

from quill_social.adapters.base import AdapterError
from quill_social.adapters.mastodon import MastodonAdapter


def status(id="1", visibility="public"):
    return {"id": id, "visibility": visibility, "content": "Hello", "account": {"acct": "ada"}}


@pytest.mark.parametrize("kind,value,method,args", [
    ("list", "9", "timeline_list", ("9",)),
    ("hashtag", "#accessibility", "timeline_hashtag", ("accessibility",)),
    ("local", "", "timeline_local", ()),
    ("user", "@ada@example.social", "account_statuses", ("7",)),
])
def test_additional_timelines(kind, value, method, args):
    client = Mock()
    client.account_lookup.return_value = {"id": "7"}
    getattr(client, method).return_value = [status()]
    rows = MastodonAdapter(client=client, account_id="own").fetch_timeline(kind, value, limit=12)
    getattr(client, method).assert_called_once_with(*args, limit=12)
    assert rows[0].account_id == "own"
    if kind == "user":
        client.account_lookup.assert_called_once_with("ada@example.social")


def test_messages_only_return_direct_conversation_statuses():
    client = Mock()
    client.conversations.return_value = [
        {"last_status": status("1", "direct")}, {"last_status": None},
        {"last_status": status("2", "public")},
    ]
    rows = MastodonAdapter(client=client).fetch_timeline("messages")
    assert [row.remote_id for row in rows] == ["1"]
    assert rows[0].visibility == "direct"


def test_lists_and_errors():
    client = Mock()
    client.lists.return_value = [{"id": 4, "title": "Friends"}]
    adapter = MastodonAdapter(client=client)
    assert adapter.timeline_lists() == [("4", "Friends")]
    client.timeline_local.side_effect = RuntimeError("offline")
    with pytest.raises(AdapterError):
        adapter.fetch_timeline("local")


def test_search_returns_posts_users_and_hashtags():
    client = Mock()
    client.search_v2.return_value = {
        "statuses": [status("post")],
        "accounts": [{"id": "7", "acct": "ada@example.social",
                      "display_name": "Ada", "note": "<p>Profile</p>",
                      "url": "https://example.social/@ada"}],
        "hashtags": [{"name": "Accessibility", "url": "https://example.social/tags/accessibility"}],
    }
    rows = MastodonAdapter(client=client, account_id="own").search("accessibility", limit=12)
    assert [row.remote_id for row in rows] == [
        "post", "search:user:7", "search:hashtag:accessibility"]
    assert rows[1].text == "User: Ada @ada@example.social. Profile"
    client.search_v2.assert_called_once_with(
        "accessibility", resolve=True, result_type=None, limit=12)


def test_search_type_is_forwarded_and_validated():
    client = Mock()
    client.search_v2.return_value = {"accounts": []}
    MastodonAdapter(client=client).search("ada", "accounts")
    assert client.search_v2.call_args.kwargs["result_type"] == "accounts"
    with pytest.raises(AdapterError):
        MastodonAdapter(client=client).search("", "statuses")


def test_remote_instance_uses_separate_unauthenticated_client(monkeypatch):
    public = Mock()
    public.timeline_local.return_value = [status()]
    constructor = Mock(return_value=public)
    monkeypatch.setattr("mastodon.Mastodon", constructor)
    authenticated = Mock()
    adapter = MastodonAdapter(client=authenticated, access_token="secret", account_id="own")
    rows = adapter.fetch_timeline("instance", "other.social")
    constructor.assert_called_once_with(api_base_url="https://other.social", request_timeout=30)
    assert not authenticated.mock_calls
    assert rows[0].remote_id == "instance:other.social:1"


@pytest.mark.parametrize("address", ["http://other.social", "https://user:pass@other.social", "other.social/path", "other.social?token=x"])
def test_instance_rejects_invalid_addresses(address):
    with pytest.raises(AdapterError, match="HTTPS instance"):
        MastodonAdapter(client=Mock()).fetch_timeline("instance", address)


def test_direct_send_resolves_recipient_and_preserves_privacy():
    client = Mock()
    client.account_lookup.return_value = {"acct": "ada@remote.social"}
    client.status_post.return_value = status("3", "direct")
    result = MastodonAdapter(client=client).send_direct_message("@ada@remote.social", "Hello")
    assert result.remote_id == "3"
    client.status_post.assert_called_once_with(
        "@ada@remote.social Hello", visibility="direct", spoiler_text=None,
        language=None, in_reply_to_id=None,
    )
    client.status_post.side_effect = RuntimeError("forbidden")
    with pytest.raises(AdapterError):
        MastodonAdapter(client=client).send_direct_message("ada", "Hello")
    assert client.status_post.call_count == 2


@pytest.mark.parametrize("recipient,text", [("", "Hello"), ("ada bob", "Hello"), ("ada", " ")])
def test_direct_send_rejects_invalid_input(recipient, text):
    client = Mock()
    with pytest.raises(AdapterError):
        MastodonAdapter(client=client).send_direct_message(recipient, text)
    assert not client.mock_calls
