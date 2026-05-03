from __future__ import annotations

from pathlib import Path

import pytest

from score2logic import cli
from score2logic.config import CommandResolutionError
from score2logic.pipeline import ConversionResult
from score2logic.quality import QualityWarning


def _missing_command(tool_name: str, env_var: str, option_name: str) -> CommandResolutionError:
    return CommandResolutionError(
        tool_name=tool_name,
        env_var=env_var,
        option_name=option_name,
        candidates=[tool_name.lower()],
    )


def _patch_doctor_with_missing_audiveris(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_audiveris(_: str | None = None) -> str:
        raise _missing_command(
            "Audiveris",
            "SCORE2LOGIC_AUDIVERIS_CMD",
            "--audiveris-cmd",
    )

    monkeypatch.setattr(cli, "resolve_audiveris_command", fail_audiveris)
    monkeypatch.setattr(
        cli,
        "resolve_musescore_command",
        lambda _: "/usr/local/bin/mscore",
    )
    monkeypatch.setattr(
        cli.shutil,
        "which",
        lambda command: "/usr/bin/sips" if command == "sips" else None,
    )


def test_cli_without_command_returns_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.app([]) == 2

    captured = capsys.readouterr()
    assert "usage: score2logic" in captured.out


def test_doctor_returns_nonzero_when_any_check_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _patch_doctor_with_missing_audiveris(monkeypatch)

    assert cli.app(["doctor", "--workdir", str(tmp_path / "work")]) == 1

    captured = capsys.readouterr()
    assert "Audiverisコマンド: 失敗" in captured.out
    assert "失敗項目があります" in captured.out


def test_doctor_warn_only_returns_zero_with_failed_checks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _patch_doctor_with_missing_audiveris(monkeypatch)

    assert cli.app(["doctor", "--workdir", str(tmp_path / "work"), "--warn-only"]) == 0

    captured = capsys.readouterr()
    assert "--warn-only" in captured.out


def test_success_output_marks_deleted_intermediates(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    workdir = tmp_path / "work"
    musicxml = workdir / "score.musicxml"
    result = ConversionResult(
        input_path=tmp_path / "score.png",
        omr_input_path=tmp_path / "score.png",
        output_midi_path=tmp_path / "out.mid",
        workdir=workdir,
        log_path=workdir / "score2logic.log",
        musicxml_candidates=[musicxml],
        selected_musicxml=musicxml,
        audiveris_cmd="audiveris",
        musescore_cmd="mscore",
        prepared_files=[],
        cleaned_files=[musicxml],
    )

    cli._print_success(result)

    captured = capsys.readouterr()
    assert f"入力: {tmp_path / 'score.png'}" in captured.out
    assert f"出力MIDI: {tmp_path / 'out.mid'}" in captured.out
    assert f"作業ディレクトリ: {workdir}" in captured.out
    assert "MusicXML:" in captured.out
    assert "削除済み" in captured.out


def test_error_output_includes_log_path(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    log_path = tmp_path / "work" / "score2logic.log"

    cli._print_error(RuntimeError("boom"), log_path=log_path)

    captured = capsys.readouterr()
    assert "boom" in captured.err
    assert f"ログ: {log_path}" in captured.err
    assert "まだログは作成されていません" in captured.err


def test_success_output_prints_quality_warnings(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    warning = QualityWarning(
        code="midi-too-small",
        message="MIDIファイルが非常に小さいです。",
        path=tmp_path / "out.mid",
    )
    result = ConversionResult(
        input_path=tmp_path / "score.png",
        omr_input_path=tmp_path / "score.png",
        output_midi_path=tmp_path / "out.mid",
        workdir=tmp_path / "work",
        log_path=tmp_path / "work" / "score2logic.log",
        musicxml_candidates=[tmp_path / "work" / "score.musicxml"],
        selected_musicxml=tmp_path / "work" / "score.musicxml",
        audiveris_cmd="audiveris",
        musescore_cmd="mscore",
        prepared_files=[],
        cleaned_files=[],
        quality_warnings=[warning],
    )

    cli._print_success(result)

    captured = capsys.readouterr()
    assert "品質チェック警告" in captured.out
    assert "midi-too-small" in captured.out


def test_batch_dry_run_prints_plan(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_dir = tmp_path / "scans"
    input_dir.mkdir()
    (input_dir / "score.png").write_bytes(b"png")

    exit_code = cli.app(
        [
            "batch",
            str(input_dir),
            "--outdir",
            str(tmp_path / "midi"),
            "--workdir",
            str(tmp_path / "work"),
            "--dry-run",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "score2logic batch dry-run" in captured.out
    assert "対象: 1件" in captured.out
    assert "score.mid" in captured.out
    assert not (tmp_path / "midi").exists()
    assert not (tmp_path / "work").exists()
