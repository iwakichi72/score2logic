from __future__ import annotations

import shlex
from datetime import datetime
from pathlib import Path


def command_to_string(command: list[str]) -> str:
    return shlex.join(command)


def append_command_log(
    *,
    log_path: Path,
    tool_name: str,
    command: list[str],
    returncode: int,
    stdout: str,
    stderr: str,
) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().isoformat(timespec="seconds")
    entry = [
        f"## {timestamp} {tool_name}",
        f"$ {command_to_string(command)}",
        f"exit_code={returncode}",
        "",
        "[stdout]",
        stdout.rstrip() or "(empty)",
        "",
        "[stderr]",
        stderr.rstrip() or "(empty)",
        "",
    ]
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(entry))
        handle.write("\n")
