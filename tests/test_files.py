from __future__ import annotations

import os
from pathlib import Path

import pytest

from score2logic.utils.files import (
    UnsupportedInputError,
    ensure_parent_directory,
    ensure_supported_input,
    find_musicxml_files,
    is_supported_input_path,
    select_latest_file,
)


@pytest.mark.parametrize(
    "filename",
    [
        "score.png",
        "score.JPG",
        "score.jpeg",
        "score.tif",
        "score.TIFF",
        "score.HEIC",
        "score.heif",
    ],
)
def test_supported_input_extensions(filename: str) -> None:
    assert is_supported_input_path(Path(filename))


def test_unsupported_extension_raises() -> None:
    with pytest.raises(UnsupportedInputError, match="未対応の入力拡張子"):
        ensure_supported_input(Path("score.txt"))


def test_pdf_is_not_supported_for_now() -> None:
    with pytest.raises(UnsupportedInputError, match="未対応の入力拡張子"):
        ensure_supported_input(Path("score.pdf"))


def test_ensure_parent_directory_returns_absolute_output_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)

    output_path = ensure_parent_directory(Path("midi/output.mid"))

    assert output_path == (tmp_path / "midi" / "output.mid").resolve()
    assert output_path.parent.is_dir()


def test_find_musicxml_files_recursively(tmp_path: Path) -> None:
    (tmp_path / "score.musicxml").write_text("<score-partwise />", encoding="utf-8")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "score.mxl").write_text("zip-ish", encoding="utf-8")
    (nested / "score.xml").write_text("<score-partwise />", encoding="utf-8")
    (nested / "notes.txt").write_text("ignore", encoding="utf-8")

    found = {path.name for path in find_musicxml_files(tmp_path)}

    assert found == {"score.musicxml", "score.mxl", "score.xml"}


def test_select_latest_file(tmp_path: Path) -> None:
    older = tmp_path / "older.musicxml"
    newer = tmp_path / "newer.musicxml"
    older.write_text("old", encoding="utf-8")
    newer.write_text("new", encoding="utf-8")
    os.utime(older, (1000, 1000))
    os.utime(newer, (2000, 2000))

    assert select_latest_file([older, newer]) == newer
