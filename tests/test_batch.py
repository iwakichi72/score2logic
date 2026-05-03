from __future__ import annotations

from pathlib import Path

import pytest

from score2logic import batch
from score2logic.batch import (
    BatchInputDirectoryError,
    build_batch_plan,
    discover_batch_inputs,
    run_batch,
)
from score2logic.config import AppConfig
from score2logic.pipeline import ConversionResult, Score2LogicError


def test_discover_batch_inputs_skips_unsupported_and_nested_by_default(tmp_path: Path) -> None:
    (tmp_path / "score.png").write_bytes(b"png")
    (tmp_path / "notes.txt").write_text("ignore", encoding="utf-8")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "nested.jpg").write_bytes(b"jpg")

    found = discover_batch_inputs(tmp_path)

    assert found == [(tmp_path / "score.png").resolve()]


def test_discover_batch_inputs_recursive_includes_nested_files(tmp_path: Path) -> None:
    (tmp_path / "score.png").write_bytes(b"png")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "nested.HEIC").write_bytes(b"heic")

    found = discover_batch_inputs(tmp_path, recursive=True)

    assert found == [
        (tmp_path / "nested" / "nested.HEIC").resolve(),
        (tmp_path / "score.png").resolve(),
    ]


def test_build_batch_plan_uses_unique_output_names_for_duplicate_stems(tmp_path: Path) -> None:
    first = tmp_path / "a"
    second = tmp_path / "b"
    first.mkdir()
    second.mkdir()
    (first / "score.png").write_bytes(b"png")
    (second / "score.jpg").write_bytes(b"jpg")

    plan = build_batch_plan(
        input_dir=tmp_path,
        output_dir=tmp_path / "midi",
        workdir=tmp_path / "work",
        recursive=True,
    )

    assert [item.output_midi_path.name for item in plan.items] == ["score.mid", "score-2.mid"]
    assert [item.workdir.name for item in plan.items] == ["score", "score-2"]


def test_build_batch_plan_dry_run_does_not_create_output_directories(tmp_path: Path) -> None:
    (tmp_path / "score.png").write_bytes(b"png")
    output_dir = tmp_path / "midi"
    workdir = tmp_path / "work"

    build_batch_plan(
        input_dir=tmp_path,
        output_dir=output_dir,
        workdir=workdir,
        create_dirs=False,
    )

    assert not output_dir.exists()
    assert not workdir.exists()


def test_build_batch_plan_invalid_input_does_not_create_output_directories(tmp_path: Path) -> None:
    output_dir = tmp_path / "midi"
    workdir = tmp_path / "work"

    with pytest.raises(BatchInputDirectoryError):
        build_batch_plan(
            input_dir=tmp_path / "missing",
            output_dir=output_dir,
            workdir=workdir,
        )

    assert not output_dir.exists()
    assert not workdir.exists()


def test_build_batch_plan_excludes_output_and_workdir_when_recursive(tmp_path: Path) -> None:
    (tmp_path / "score.png").write_bytes(b"png")
    output_dir = tmp_path / "midi"
    output_dir.mkdir()
    (output_dir / "existing.png").write_bytes(b"png")
    workdir = tmp_path / "work"
    workdir.mkdir()
    (workdir / "prepared.png").write_bytes(b"png")

    plan = build_batch_plan(
        input_dir=tmp_path,
        output_dir=output_dir,
        workdir=workdir,
        recursive=True,
    )

    assert [item.input_path.name for item in plan.items] == ["score.png"]


def test_run_batch_continues_after_item_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    plan = _plan_with_inputs(tmp_path, ["bad.png", "good.png"])
    monkeypatch.setattr(batch, "resolve_audiveris_command", lambda _: "/bin/audiveris")
    monkeypatch.setattr(batch, "resolve_musescore_command", lambda _: "/bin/mscore")
    monkeypatch.setattr(batch, "convert_score_to_midi", _fake_convert_with_bad_file)

    result = run_batch(plan, AppConfig())

    assert result.attempted_count == 2
    assert result.success_count == 1
    assert result.failure_count == 1
    assert result.items[0].error is not None
    assert result.items[1].succeeded


def test_run_batch_fail_fast_stops_after_first_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    plan = _plan_with_inputs(tmp_path, ["bad.png", "good.png"])
    monkeypatch.setattr(batch, "resolve_audiveris_command", lambda _: "/bin/audiveris")
    monkeypatch.setattr(batch, "resolve_musescore_command", lambda _: "/bin/mscore")
    monkeypatch.setattr(batch, "convert_score_to_midi", _fake_convert_with_bad_file)

    result = run_batch(plan, AppConfig(), fail_fast=True)

    assert result.attempted_count == 1
    assert result.success_count == 0
    assert result.failure_count == 1


def _plan_with_inputs(tmp_path: Path, filenames: list[str]):
    for filename in filenames:
        (tmp_path / filename).write_bytes(b"image")
    return build_batch_plan(
        input_dir=tmp_path,
        output_dir=tmp_path / "midi",
        workdir=tmp_path / "work",
    )


def _fake_convert_with_bad_file(
    input_path: Path,
    output_path: Path,
    config: AppConfig,
) -> ConversionResult:
    if input_path.name == "bad.png":
        raise Score2LogicError("bad score")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(b"MThd")
    musicxml = Path(config.workdir) / f"{input_path.stem}.musicxml"
    musicxml.parent.mkdir(parents=True, exist_ok=True)
    musicxml.write_text("<score-partwise />", encoding="utf-8")
    return ConversionResult(
        input_path=input_path,
        omr_input_path=input_path,
        output_midi_path=output_path,
        workdir=Path(config.workdir),
        log_path=Path(config.workdir) / "score2logic.log",
        musicxml_candidates=[musicxml],
        selected_musicxml=musicxml,
        audiveris_cmd=str(config.audiveris_cmd),
        musescore_cmd=str(config.musescore_cmd),
        prepared_files=[],
        cleaned_files=[],
    )
