from __future__ import annotations

from pathlib import Path

import pytest

from score2logic.external import CommandExecutionError
from score2logic.external.sips import convert_heic_to_png


class _Completed:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_convert_heic_to_png_runs_sips(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    input_file = tmp_path / "score.heic"
    input_file.write_bytes(b"heic")
    workdir = tmp_path / "work"
    workdir.mkdir()
    captured_command: list[str] = []

    def fake_run(command, **kwargs):
        captured_command.extend(command)
        output_path = Path(command[command.index("--out") + 1])
        output_path.write_bytes(b"png")
        return _Completed(returncode=0, stdout="ok")

    monkeypatch.setattr("score2logic.external.sips.subprocess.run", fake_run)

    output = convert_heic_to_png(input_file, workdir)

    assert output == workdir / "score.score2logic.png"
    assert output.read_bytes() == b"png"
    assert captured_command[:4] == ["sips", "-s", "format", "png"]
    assert captured_command[-2:] == ["--out", str(output)]


def test_convert_heic_to_png_raises_on_sips_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    input_file = tmp_path / "score.heic"
    input_file.write_bytes(b"heic")
    workdir = tmp_path / "work"
    workdir.mkdir()

    monkeypatch.setattr(
        "score2logic.external.sips.subprocess.run",
        lambda *_, **__: _Completed(returncode=1, stderr="bad image"),
    )

    with pytest.raises(CommandExecutionError, match="sips の実行に失敗しました"):
        convert_heic_to_png(input_file, workdir)
