from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from score2logic.external import CommandExecutionError
from score2logic.utils.logging import append_command_log, command_to_string


def convert_musicxml_to_midi(
    musicxml_path: Path,
    output_midi_path: Path,
    musescore_cmd: str,
    verbose: bool = False,
    log_path: Path | None = None,
) -> Path:
    """Convert MusicXML to MIDI by delegating to MuseScore CLI."""

    output_midi_path.parent.mkdir(parents=True, exist_ok=True)
    command = [musescore_cmd, str(musicxml_path), "-o", str(output_midi_path)]
    log_path = log_path or musicxml_path.parent / "score2logic.log"

    if verbose:
        print(f"[score2logic] MuseScore: {command_to_string(command)}", file=sys.stderr)

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        stderr = str(exc)
        append_command_log(
            log_path=log_path,
            tool_name="MuseScore",
            command=command,
            returncode=127,
            stdout="",
            stderr=stderr,
        )
        raise CommandExecutionError(
            tool_name="MuseScore",
            command=command,
            returncode=127,
            stdout="",
            stderr=stderr,
        ) from exc

    append_command_log(
        log_path=log_path,
        tool_name="MuseScore",
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
            tool_name="MuseScore",
            command=command,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    return output_midi_path
