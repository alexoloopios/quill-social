import json

import pytest

from quill_social.services import settings_backup as backups


def test_round_trip_preserves_preferences_shortcuts_and_excludes_database(tmp_path):
    preferences = tmp_path / "a11y.json"
    shortcuts = tmp_path / "keymap.json"
    preferences.write_text('{"ui_mode":"advanced","display_timezone":"utc"}')
    shortcuts.write_text('{"compose":"Alt+N"}')
    database = tmp_path / "social.db"
    database.write_bytes(b"private accounts and drafts")
    saved = backups.create_backup(tmp_path)
    assert set(backups.read_backup(saved)["files"]) == set(backups.FILES)
    preferences.write_text('{"ui_mode":"standard"}')
    shortcuts.write_text('{}')
    recovery = backups.restore_backup(saved, tmp_path)
    assert json.loads(preferences.read_text())["ui_mode"] == "advanced"
    assert json.loads(shortcuts.read_text())["compose"] == "Alt+N"
    assert backups.read_backup(recovery)["files"]["a11y.json"] == {"ui_mode": "standard"}
    assert database.read_bytes() == b"private accounts and drafts"


def test_defaults_and_unchanged_backup(tmp_path):
    saved = backups.create_backup(tmp_path)
    assert backups.create_backup(tmp_path, only_if_changed=True) == saved
    (tmp_path / "a11y.json").write_text('{"ui_mode":"advanced"}')
    backups.restore_backup(saved, tmp_path)
    assert not (tmp_path / "a11y.json").exists()


@pytest.mark.parametrize("mutation", [
    lambda data: data.update(format="leasey"),
    lambda data: data.update(version=2),
    lambda data: data["files"].update({"../accounts.json": {}}),
    lambda data: data["files"].update({"a11y.json": {"ui_mode": "broken"}}),
    lambda data: data["files"].update({"a11y.json": {"high_contrast": "false"}}),
    lambda data: data["files"].update({"keymap.json": {"compose": 5}}),
])
def test_invalid_backup_rejected_before_settings_change(tmp_path, mutation):
    settings = tmp_path / "a11y.json"
    settings.write_text('{"ui_mode":"standard"}')
    saved = backups.create_backup(tmp_path)
    data = backups.read_backup(saved)
    mutation(data)
    saved.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        backups.restore_backup(saved, tmp_path)
    assert settings.read_text() == '{"ui_mode":"standard"}'
    assert len(backups.list_backups(tmp_path)) == 1


def test_second_write_failure_rolls_back_exact_original_bytes(tmp_path, monkeypatch):
    prefs = tmp_path / "a11y.json"
    keys = tmp_path / "keymap.json"
    prefs.write_text('{"ui_mode":"advanced"}')
    keys.write_text('{"compose":"Alt+N"}')
    saved = backups.create_backup(tmp_path)
    original = b'{ "ui_mode" : "standard" }\n'
    prefs.write_bytes(original)
    keys.unlink()
    real_write = backups._atomic_write

    def fail_keys(path, content):
        if path == keys:
            raise OSError("disk write failed")
        return real_write(path, content)

    monkeypatch.setattr(backups, "_atomic_write", fail_keys)
    with pytest.raises(OSError, match="disk write failed"):
        backups.restore_backup(saved, tmp_path)
    assert prefs.read_bytes() == original
    assert not keys.exists()
    assert len(backups.list_backups(tmp_path)) == 2
