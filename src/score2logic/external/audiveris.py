from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from score2logic.external import CommandExecutionError
from score2logic.utils.files import find_musicxml_files
from score2logic.utils.logging import append_command_log, command_to_string


def run_audiveris(
    input_path: Path,
    workdir: Path,
    audiveris_cmd: str,
    verbose: bool = False,
) -> list[Path]:
    """Run Audiveris OMR and return MusicXML candidates found in workdir."""

    command = [
        audiveris_cmd,
        "-batch",
        "-export",
        "-output",
        str(workdir),
        "--",
        str(input_path),
    ]
    log_path = workdir / "score2logic.log"

    if verbose:
        print(f"[score2logic] Audiveris: {command_to_string(command)}", file=sys.stderr)

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
            tool_name="Audiveris",
            command=command,
            returncode=127,
            stdout="",
            stderr=stderr,
        )
        raise CommandExecutionError(
            tool_name="Audiveris",
            command=command,
            returncode=127,
            stdout="",
            stderr=stderr,
        ) from exc

    append_command_log(
        log_path=log_path,
        tool_name="Audiveris",
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
            tool_name="Audiveris",
            command=command,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    return find_musicxml_files(workdir)
