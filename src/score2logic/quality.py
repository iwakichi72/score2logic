from __future__ import annotations

import struct
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree


class QualityCheckError(RuntimeError):
    """Raised when a generated intermediate is too broken to inspect safely."""


class MusicXMLValidationError(QualityCheckError):
    def __init__(self, path: Path, reason: str) -> None:
        self.path = path
        self.reason = reason
        super().__init__(
            "MusicXMLを読み取れません。\n"
            f"パス: {path}\n"
            f"理由: {reason}\n"
            "Audiverisの出力を確認するため、--keep --verbose 付きで再実行してください。"
        )


@dataclass(frozen=True)
class QualityWarning:
    code: str
    message: str
    path: Path

    def format(self) -> str:
        return f"{self.code}: {self.message} ({self.path})"


def inspect_musicxml(path: Path) -> list[QualityWarning]:
    """Run lightweight MusicXML structure checks."""

    root = _read_musicxml_root(path)
    root_name = _local_name(root.tag)
    warnings: list[QualityWarning] = []

    if root_name not in {"score-partwise", "score-timewise"}:
        warnings.append(
            QualityWarning(
                code="musicxml-root",
                message=f"MusicXMLのルート要素が想定外です: {root_name}",
                path=path,
            )
        )

    if not _has_descendant(root, "part"):
        warnings.append(
            QualityWarning(
                code="musicxml-no-part",
                message="part要素が見つかりません。譜面認識が空に近い可能性があります。",
                path=path,
            )
        )

    if not _has_descendant(root, "note"):
        warnings.append(
            QualityWarning(
                code="musicxml-no-note",
                message="note要素が見つかりません。MIDIが空に近い可能性があります。",
                path=path,
            )
        )

    return warnings


def inspect_midi(path: Path) -> list[QualityWarning]:
    """Run lightweight MIDI file checks without parsing musical content."""

    size = path.stat().st_size
    warnings: list[QualityWarning] = []

    if size == 0:
        return [
            QualityWarning(
                code="midi-empty",
                message="MIDIファイルが空です。",
                path=path,
            )
        ]

    if size < 14:
        warnings.append(
            QualityWarning(
                code="midi-too-small",
                message=f"MIDIファイルが非常に小さいです ({size} bytes)。",
                path=path,
            )
        )
        return warnings

    with path.open("rb") as handle:
        header = handle.read(14)

    if header[:4] != b"MThd":
        warnings.append(
            QualityWarning(
                code="midi-missing-header",
                message="MIDIヘッダ MThd が見つかりません。",
                path=path,
            )
        )
        return warnings

    header_length, _, track_count, _ = struct.unpack(">IHHH", header[4:14])
    if header_length != 6:
        warnings.append(
            QualityWarning(
                code="midi-header-length",
                message=f"MIDIヘッダ長が想定外です: {header_length}",
                path=path,
            )
        )
    if track_count == 0:
        warnings.append(
            QualityWarning(
                code="midi-no-track",
                message="MIDIトラック数が0です。",
                path=path,
            )
        )
    if size < 64:
        warnings.append(
            QualityWarning(
                code="midi-very-small",
                message=f"MIDIファイルがかなり小さいです ({size} bytes)。",
                path=path,
            )
        )

    return warnings


def _read_musicxml_root(path: Path) -> ElementTree.Element:
    if path.suffix.lower() == ".mxl":
        return _read_mxl_root(path)
    try:
        return ElementTree.parse(path).getroot()
    except ElementTree.ParseError as exc:
        raise MusicXMLValidationError(path, str(exc)) from exc
    except OSError as exc:
        raise MusicXMLValidationError(path, str(exc)) from exc


def _read_mxl_root(path: Path) -> ElementTree.Element:
    try:
        with zipfile.ZipFile(path) as archive:
            rootfile = _find_mxl_rootfile(archive)
            with archive.open(rootfile) as handle:
                return ElementTree.parse(handle).getroot()
    except (KeyError, OSError, zipfile.BadZipFile, ElementTree.ParseError) as exc:
        raise MusicXMLValidationError(path, str(exc)) from exc


def _find_mxl_rootfile(archive: zipfile.ZipFile) -> str:
    try:
        with archive.open("META-INF/container.xml") as handle:
            container = ElementTree.parse(handle).getroot()
    except KeyError:
        for name in archive.namelist():
            if name.lower().endswith((".musicxml", ".xml")):
                return name
        raise

    for element in container.iter():
        if _local_name(element.tag) == "rootfile":
            full_path = element.attrib.get("full-path")
            if full_path:
                return full_path
    raise KeyError("META-INF/container.xml に rootfile が見つかりません")


def _has_descendant(root: ElementTree.Element, name: str) -> bool:
    return any(_local_name(element.tag) == name for element in root.iter())


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
