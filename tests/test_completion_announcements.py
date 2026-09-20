from types import SimpleNamespace

import pytest

from quill_social.adapters.base import AdapterError, PublishResult
from quill_social.model import Draft, PublicationPlan
from quill_social.services.scheduler import StepResult

wx = pytest.importorskip("wx")


@pytest.fixture
def frame(tmp_path, monkeypatch):
    from quill_social.ui.app import SocialFrame
    monkeypatch.setenv("QUILLSOCIAL_DATA", str(tmp_path))
    app = wx.App()
    window = SocialFrame()
    window.spoken = []
    window.errors = []
    monkeypatch.setattr(window.announcer, "say", lambda text, *a, **kw: window.spoken.append(text))
    monkeypatch.setattr(window.announcer, "error", window.errors.append)
    yield window
    window._on_close(None)
    app.Destroy()


@pytest.mark.parametrize("fail", [False, True])
def test_thread_progress_and_final_outcome(frame, monkeypatch, fail):
    from quill_social.ui import app as module
    pending = []
    monkeypatch.setattr(module, "Thread", lambda target, **kw: SimpleNamespace(start=lambda: pending.append(target)))
    monkeypatch.setattr(wx, "CallAfter", lambda fn, *args: fn(*args))
    monkeypatch.setattr(frame, "_refresh_from_network", lambda **kw: None)
    monkeypatch.setattr(module, "split_thread", lambda *a, **kw: SimpleNamespace(texts=lambda: ["one", "two"]))
    sent = []
    def publish(request):
        if fail and sent:
            raise AdapterError("Server refused second part")
        sent.append(request.text)
        return PublishResult(str(len(sent)))
    monkeypatch.setattr(module, "adapter_for", lambda *args: SimpleNamespace(publish=publish))
    frame._publish_now(Draft(text="A thread", targets=[frame.store.list_accounts()[0].account_id], thread_mode=True))
    assert frame._publishing
    assert not sent
    pending.pop()()
    assert not frame._publishing
    assert any("Thread part 1 of 2 sent" in text for text in frame.spoken)
    if fail:
        assert sent == ["one"]
        assert "Published 1 of 2" in frame.errors[-1]
        assert "Server refused" in frame.errors[-1]
        assert not any("Thread sent." in text for text in frame.spoken)
    else:
        assert sent == ["one", "two"]
        assert "Thread sent. 2 parts." in frame.spoken[-1]


def test_scheduler_announces_retry_and_failure(frame, monkeypatch):
    account = frame.store.list_accounts()[0]
    plan = PublicationPlan(account_id=account.account_id, next_retry_at=1000)
    results = [StepResult(plan, False, False, True, "Retry in 30s."),
               StepResult(plan, False, True, False, "Permission denied.")]
    monkeypatch.setattr(frame.scheduler, "run_due", lambda: results)
    frame._on_sched_tick(None)
    assert "Queued to retry" in frame.errors[0]
    assert "Permission denied" in frame.errors[1]


def test_link_success_and_failure(frame, monkeypatch):
    from quill_social.ui import app as module
    monkeypatch.setattr(module.webbrowser, "open", lambda url: True)
    frame._open_announced_link("https://example.org")
    assert frame.spoken[-1] == "Opened link."
    monkeypatch.setattr(module.webbrowser, "open", lambda url: False)
    frame._open_announced_link("https://example.org")
    assert "Could not open link" in frame.errors[-1]


def test_profile_success_announced_but_failure_not(frame, monkeypatch):
    from quill_social.ui.profile import ProfileDialog
    monkeypatch.setattr(ProfileDialog, "_run", lambda *args: None)
    dialog = ProfileDialog(frame, lambda: None)
    monkeypatch.setattr(dialog, "EndModal", lambda result: None)
    try:
        dialog._saved(None, None)
        assert frame.spoken == ["Profile updated."]
        dialog._saved(None, "Rejected")
        assert frame.spoken == ["Profile updated."]
    finally:
        dialog.Destroy()
