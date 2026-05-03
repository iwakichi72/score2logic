from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Iterable

HEIC_INPUT_EXTENSIONS = {".heic", ".heif"}
SUPPORTED_INPUT_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".tif",
    ".tiff",
    *HEIC_INPUT_EXTENSIONS,
}
MUSICXML_EXTENSIONS = {".musicxml", ".mxl", ".xml"}


class FileValidationError(ValueError):
    """Base class for file validation errors."""


class MissingInputFileError(FileValidationError):
    def __init__(self, path: Path) -> None:
        self.path = path
        super().__init__(
            "入力ファイルが見つかりません。\n"
            f"パス: {path}\n"
            "ファイルパスを確認してから再実行してください。"
        )


class UnsupportedInputError(FileValidationError):
    def __init__(self, path: Path) -> None:
        self.path = path
        super().__init__(
            "未対応の入力拡張子です。\n"
            f"パス: {path}\n"
            f"対応拡張子: {supported_input_extensions_text()}"
        )


def supported_input_extensions_text() -> str:
    return ", ".join(sorted(SUPPORTED_INPUT_EXTENSIONS))


def is_supported_input_path(path: Path | str) -> bool:
    return Path(path).suffix.lower() in SUPPORTED_INPUT_EXTENSIONS


def is_heic_input_path(path: Path | str) -> bool:
    return Path(path).suffix.lower() in HEIC_INPUT_EXTENSIONS


def ensure_existing_file(path: Path | str) -> Path:
    resolved = Path(path).expanduser().resolve()
    if not resolved.is_file():
        raise MissingInputFileError(resolved)
    return resolved


def ensure_supported_input(path: Path | str) -> Path:
    resolved = Path(path).expanduser().resolve()
    if not is_supported_input_path(resolved):
        raise UnsupportedInputError(resolved)
    return resolved


def ensure_directory(path: Path | str) -> Path:
    resolved = Path(path).expanduser().resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def ensure_parent_directory(path: Path | str) -> Path:
    resolved = Path(path).expanduser()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return resolved.resolve()


def check_writable_directory(path: Path | str) -> tuple[bool, str | None]:
    directory = Path(path).expanduser().resolve()
    try:
        directory.mkdir(parents=True, exist_ok=True)
        probe = directory / f".score2logic-write-test-{uuid.uuid4().hex}"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True, None
    except OSError as exc:
        return False, str(exc)


def find_musicxml_files(workdir: Path | str) -> list[Path]:
    directory = Path(workdir).expanduser()
    if not directory.exists():
        return []

    files = [
        path
        for path in directory.rglob("*")
        if path.is_file() and path.suffix.lower() in MUSICXML_EXTENSIONS
    ]
    return sorted(files, key=lambda path: str(path))


def select_latest_file(paths: Iterable[Path]) -> Path:
    candidates = list(paths)
    if not candidates:
        raise ValueError("ファイル候補がありません。")
    return max(candidates, key=lambda path: (_mtime_ns(path), str(path)))


def snapshot_mtimes(paths: Iterable[Path]) -> dict[Path, int]:
    snapshot: dict[Path, int] = {}
    for path in paths:
        try:
            snapshot[path.resolve()] = path.stat().st_mtime_ns
        except FileNotFoundError:
            continue
    return snapshot


def changed_since_snapshot(paths: Iterable[Path], snapshot: dict[Path, int]) -> list[Path]:
    changed: list[Path] = []
    for path in paths:
        resolved = path.resolve()
        before = snapshot.get(resolved)
        try:
            after = path.stat().st_mtime_ns
        except FileNotFoundError:
            continue
        if before is None or before != after:
            changed.append(path)
    return changed


def remove_files(paths: Iterable[Path]) -> list[Path]:
    removed: list[Path] = []
    for path in paths:
        try:
            path.unlink()
            removed.append(path)
        except FileNotFoundError:
            continue
        except IsADirectoryError:
            continue
    return removed


def _mtime_ns(path: Path) -> int:
    return os.stat(path).st_mtime_ns
