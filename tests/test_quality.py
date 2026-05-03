from __future__ import annotations

import struct
import zipfile
from pathlib import Path

import pytest

from score2logic.quality import (
    MusicXMLValidationError,
    inspect_midi,
    inspect_musicxml,
)


def test_inspect_musicxml_accepts_basic_score(tmp_path: Path) -> None:
    musicxml = tmp_path / "score.musicxml"
    musicxml.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="4.0">
  <part id="P1">
    <measure number="1">
      <note><rest/><duration>1</duration></note>
    </measure>
  </part>
</score-partwise>
""",
        encoding="utf-8",
    )

    assert inspect_musicxml(musicxml) == []


def test_inspect_musicxml_warns_when_notes_are_missing(tmp_path: Path) -> None:
    musicxml = tmp_path / "empty.musicxml"
    musicxml.write_text("<score-partwise />", encoding="utf-8")

    warnings = inspect_musicxml(musicxml)

    assert {warning.code for warning in warnings} == {
        "musicxml-no-part",
        "musicxml-no-note",
    }


def test_inspect_musicxml_raises_for_invalid_xml(tmp_path: Path) -> None:
    musicxml = tmp_path / "broken.musicxml"
    musicxml.write_text("<score-partwise>", encoding="utf-8")

    with pytest.raises(MusicXMLValidationError, match="MusicXMLを読み取れません"):
        inspect_musicxml(musicxml)


def test_inspect_mxl_uses_container_rootfile(tmp_path: Path) -> None:
    mxl = tmp_path / "score.mxl"
    with zipfile.ZipFile(mxl, "w") as archive:
        archive.writestr(
            "META-INF/container.xml",
            """<container>
  <rootfiles><rootfile full-path="score.musicxml" /></rootfiles>
</container>""",
        )
        archive.writestr(
            "score.musicxml",
            "<score-partwise><part><measure><note /></measure></part></score-partwise>",
        )

    assert inspect_musicxml(mxl) == []


def test_inspect_midi_warns_for_tiny_file(tmp_path: Path) -> None:
    midi = tmp_path / "tiny.mid"
    midi.write_bytes(b"MThd")

    warnings = inspect_midi(midi)

    assert [warning.code for warning in warnings] == ["midi-too-small"]


def test_inspect_midi_warns_for_missing_header(tmp_path: Path) -> None:
    midi = tmp_path / "not-midi.mid"
    midi.write_bytes(b"not a midi file")

    warnings = inspect_midi(midi)

    assert [warning.code for warning in warnings] == ["midi-missing-header"]


def test_inspect_midi_accepts_basic_header(tmp_path: Path) -> None:
    midi = tmp_path / "ok.mid"
    header = b"MThd" + struct.pack(">IHHH", 6, 0, 1, 480)
    midi.write_bytes(header + b"\0" * 64)

    assert inspect_midi(midi) == []
