from __future__ import annotations

import os
from pathlib import Path

import pytest

from score2logic.config import AppConfig
from score2logic.external import CommandExecutionError
from score2logic.pipeline import (
    MidiNotGeneratedError,
    MusicXMLNotGeneratedError,
    convert_score_to_midi,
)
from score2logic.utils.files import UnsupportedInputError


def test_pipeline_rejects_unsupported_extension(tmp_path: Path) -> None:
    input_file = tmp_path / "score.txt"
    input_file.write_text("not a score", encoding="utf-8")

    with pytest.raises(UnsupportedInputError):
        convert_score_to_midi(
            input_file,
            tmp_path / "out.mid",
            AppConfig(
                workdir=tmp_path / "work",
                audiveris_cmd="/bin/echo",
                musescore_cmd="/bin/echo",
            ),
        )


def test_pipeline_raises_external_command_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    input_file = tmp_path / "score.png"
    input_file.write_bytes(b"image")

    monkeypatch.setattr("score2logic.pipeline.resolve_audiveris_command", lambda _: "/bin/audiveris")
    monkeypatch.setattr("score2logic.pipeline.resolve_musescore_command", lambda _: "/bin/mscore")

    def fail_audiveris(*args, **kwargs):
        raise CommandExecutionError(
            tool_name="Audiveris",
            command=["audiveris"],
            returncode=2,
            stdout="",
            stderr="boom",
        )

    monkeypatch.setattr("score2logic.pipeline.run_audiveris", fail_audiveris)

    with pytest.raises(CommandExecutionError, match="Audiveris の実行に失敗しました"):
        convert_score_to_midi(
            input_file,
            tmp_path / "out.mid",
            AppConfig(workdir=tmp_path / "work"),
        )


def test_pipeline_raises_when_musicxml_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    input_file = tmp_path / "score.png"
    input_file.write_bytes(b"image")

    monkeypatch.setattr("score2logic.pipeline.resolve_audiveris_command", lambda _: "/bin/audiveris")
    monkeypatch.setattr("score2logic.pipeline.resolve_musescore_command", lambda _: "/bin/mscore")
    monkeypatch.setattr("score2logic.pipeline.run_audiveris", lambda **_: [])

    with pytest.raises(MusicXMLNotGeneratedError, match="MusicXMLが生成されませんでした"):
        convert_score_to_midi(
            input_file,
            tmp_path / "out.mid",
            AppConfig(workdir=tmp_path / "work"),
        )


def test_pipeline_ignores_stale_musicxml(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    input_file = tmp_path / "score.png"
    input_file.write_bytes(b"image")
    workdir = tmp_path / "work"
    workdir.mkdir()
    stale = workdir / "old.musicxml"
    stale.write_text("<score-partwise />", encoding="utf-8")
    os.utime(stale, (1000, 1000))

    monkeypatch.setattr("score2logic.pipeline.resolve_audiveris_command", lambda _: "/bin/audiveris")
    monkeypatch.setattr("score2logic.pipeline.resolve_musescore_command", lambda _: "/bin/mscore")
    monkeypatch.setattr("score2logic.pipeline.run_audiveris", lambda **_: [stale])

    with pytest.raises(MusicXMLNotGeneratedError, match="新規作成または更新された"):
        convert_score_to_midi(
            input_file,
            tmp_path / "out.mid",
            AppConfig(workdir=workdir),
        )


def test_pipeline_uses_latest_musicxml_and_generates_midi(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    input_file = tmp_path / "score.png"
    input_file.write_bytes(b"image")
    workdir = tmp_path / "work"

    monkeypatch.setattr("score2logic.pipeline.resolve_audiveris_command", lambda _: "/bin/audiveris")
    monkeypatch.setattr("score2logic.pipeline.resolve_musescore_command", lambda _: "/bin/mscore")

    def fake_audiveris(**kwargs):
        work = kwargs["workdir"]
        work.mkdir(parents=True, exist_ok=True)
        older = work / "older.musicxml"
        newer = work / "newer.musicxml"
        older.write_text("<score-partwise />", encoding="utf-8")
        newer.write_text("<score-partwise />", encoding="utf-8")
        os.utime(older, (1000, 1000))
        os.utime(newer, (2000, 2000))
        return [older, newer]

    def fake_musescore(musicxml_path, output_midi_path, **kwargs):
        assert musicxml_path.name == "newer.musicxml"
        output_midi_path.write_bytes(b"MThd")
        return output_midi_path

    monkeypatch.setattr("score2logic.pipeline.run_audiveris", fake_audiveris)
    monkeypatch.setattr("score2logic.pipeline.convert_musicxml_to_midi", fake_musescore)

    result = convert_score_to_midi(
        input_file,
        tmp_path / "out.mid",
        AppConfig(workdir=workdir, keep=True),
    )

    assert result.output_midi_path.is_file()
    assert result.selected_musicxml.name == "newer.musicxml"


def test_pipeline_raises_when_midi_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    input_file = tmp_path / "score.png"
    input_file.write_bytes(b"image")
    musicxml = tmp_path / "work" / "score.musicxml"

    monkeypatch.setattr("score2logic.pipeline.resolve_audiveris_command", lambda _: "/bin/audiveris")
    monkeypatch.setattr("score2logic.pipeline.resolve_musescore_command", lambda _: "/bin/mscore")

    def fake_audiveris(**kwargs):
        musicxml.parent.mkdir(parents=True, exist_ok=True)
        musicxml.write_text("<score-partwise />", encoding="utf-8")
        return [musicxml]

    monkeypatch.setattr("score2logic.pipeline.run_audiveris", fake_audiveris)
    monkeypatch.setattr(
        "score2logic.pipeline.convert_musicxml_to_midi",
        lambda musicxml_path, output_midi_path, **kwargs: output_midi_path,
    )

    with pytest.raises(MidiNotGeneratedError, match="MIDIファイルが生成されませんでした"):
        convert_score_to_midi(
            input_file,
            tmp_path / "out.mid",
            AppConfig(workdir=tmp_path / "work", keep=True),
        )
