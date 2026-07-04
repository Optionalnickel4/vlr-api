"""Unit tests for app.cs2.grab_cf's .env rewrite logic.

The browser-driving parts of grab_cf.py (nodriver launch, challenge polling)
aren't unit-testable without a real Chromium + live HLTV — that's exercised
manually by running the script for real. This file covers the one piece that
IS deterministic: rewriting HLTV_CF_CLEARANCE / HLTV_USER_AGENT into .env
without disturbing anything else in the file.
"""
import importlib


def _reload_with_env_path(monkeypatch, tmp_path):
    """Import grab_cf with ENV_PATH pointed at a scratch file."""
    import app.cs2.grab_cf as grab_cf

    env_file = tmp_path / ".env"
    monkeypatch.setattr(grab_cf, "ENV_PATH", env_file)
    return grab_cf, env_file


def test_adds_new_keys_when_absent(monkeypatch, tmp_path):
    grab_cf, env_file = _reload_with_env_path(monkeypatch, tmp_path)
    env_file.write_text("VLR_REDIS_URL=redis://localhost:6379/0\n", encoding="utf-8")

    grab_cf._update_env("cookievalue123", "Mozilla/5.0 test-ua")

    content = env_file.read_text(encoding="utf-8")
    assert "VLR_REDIS_URL=redis://localhost:6379/0" in content
    assert "HLTV_CF_CLEARANCE=cookievalue123" in content
    assert "HLTV_USER_AGENT=Mozilla/5.0 test-ua" in content


def test_overwrites_existing_keys_in_place(monkeypatch, tmp_path):
    grab_cf, env_file = _reload_with_env_path(monkeypatch, tmp_path)
    env_file.write_text(
        "VLR_REDIS_URL=redis://localhost:6379/0\n"
        "HLTV_CF_CLEARANCE=stale-cookie\n"
        "HLTV_USER_AGENT=stale-ua\n"
        "VLR_ENABLE_SCHEDULER=true\n",
        encoding="utf-8",
    )

    grab_cf._update_env("fresh-cookie", "fresh-ua")

    lines = env_file.read_text(encoding="utf-8").splitlines()
    assert lines.count("HLTV_CF_CLEARANCE=fresh-cookie") == 1
    assert lines.count("HLTV_USER_AGENT=fresh-ua") == 1
    assert "VLR_ENABLE_SCHEDULER=true" in lines
    assert "VLR_REDIS_URL=redis://localhost:6379/0" in lines
    # no duplicate/stale lines left behind
    assert not any("stale-cookie" in l or "stale-ua" in l for l in lines)


def test_missing_env_file_exits_with_error(monkeypatch, tmp_path, capsys):
    grab_cf, env_file = _reload_with_env_path(monkeypatch, tmp_path)
    assert not env_file.exists()

    try:
        grab_cf._update_env("x", "y")
        assert False, "expected SystemExit"
    except SystemExit as e:
        assert e.code == 1
    err = capsys.readouterr().err
    assert ".env does not exist" in err
