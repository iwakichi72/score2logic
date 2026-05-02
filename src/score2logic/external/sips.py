from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from score2logic.external import CommandExecutionError
from score2logic.utils.logging import append_command_log, command_to_string


def convert_heic_to_png(
    input_path: Path,
    workdir: Path,
    verbose: bool = False,
) -> Path:
    """Convert a HEIC/HEIF image into a PNG file using macOS sips."""

    output_path = _prepared_png_path(input_path, workdir)
    command = ["sips", "-s", "format", "png", str(input_path), "--out", str(output_path)]
    log_path = workdir / "score2logic.log"

    if verbose:
        print(f"[score2logic] sips: {command_to_string(command)}", file=sys.stderr)

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        stderr = (
            f"{exc}\n"
            "HEIC/HEIF入力はmacOS標準の sips コマンドでPNGへ変換します。"
            "macOS上で実行しているか、sips が利用できるか確認してください。"
        )
        append_command_log(
            log_path=log_path,
            tool_name="sips",
            command=command,
            returncode=127,
            stdout="",
            stderr=stderr,
        )
        raise CommandExecutionError(
            tool_name="sips",
            command=command,
            returncode=127,
            stdout="",
            stderr=stderr,
        ) from exc

    append_command_log(
        log_path=log_path,
        tool_name="sips",
        command=command,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )

    if verbose and completed.stdout:
        print(completed.stdout, file=sys.stderr)
    if verbose and completed.stderr:
        print(completed.stderr, file=sys.stderr)

    if completed.returncode != 0:
        raise CommandExecutionError(
            tool_name="sips",
            command=command,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    return output_path


def _prepared_png_path(input_path: Path, workdir: Path) -> Path:
    stem = input_path.stem or "input"
    base = workdir / f"{stem}.score2logic.png"
    if not base.exists():
        return base

    for index in range(1, 1000):
        candidate = workdir / f"{stem}.score2logic-{index}.png"
        if not candidate.exists():
            return candidate

    return workdir / f"{stem}.score2logic-{input_path.stat().st_mtime_ns}.png"
