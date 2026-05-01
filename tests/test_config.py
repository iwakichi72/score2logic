from __future__ import annotations

from pathlib import Path

import pytest

from score2logic import config
from score2logic.config import CommandResolutionError


def _make_executable(path: Path) -> Path:
    path.write_text("#!/bin/sh\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def test_resolve_audiveris_explicit_path(tmp_path: Path) -> None:
    audiveris = _make_executable(tmp_path / "audiveris")

    assert config.resolve_audiveris_command(str(audiveris)) == str(audiveris)


def test_resolve_audiveris_env_priority(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    audiveris = _make_executable(tmp_path / "env-audiveris")
    monkeypatch.setenv(config.AUDIVERIS_ENV, str(audiveris))

    assert config.resolve_audiveris_command() == str(audiveris)


def test_resolve_musescore_prefers_mscore_on_path(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_which(command: str) -> str | None:
        if command == "mscore":
            return "/usr/local/bin/mscore"
        if command == "musescore":
            return "/usr/local/bin/musescore"
        return None

    monkeypatch.delenv(config.MUSESCORE_ENV, raising=False)
    monkeypatch.setattr(config.shutil, "which", fake_which)

    assert config.resolve_musescore_command() == "/usr/local/bin/mscore"


def test_resolve_musescore_missing_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(config.MUSESCORE_ENV, raising=False)
    monkeypatch.setattr(config.shutil, "which", lambda _: None)

    with pytest.raises(CommandResolutionError, match="MuseScore コマンドが見つかりません"):
        config.resolve_musescore_command()
