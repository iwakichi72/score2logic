from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

AUDIVERIS_ENV = "SCORE2LOGIC_AUDIVERIS_CMD"
MUSESCORE_ENV = "SCORE2LOGIC_MUSESCORE_CMD"
AUDIVERIS_MACOS_CANDIDATES = [
    "/Applications/Audiveris.app/Contents/MacOS/Audiveris",
]
MUSESCORE_MACOS_CANDIDATES = [
    "/Applications/MuseScore 4.app/Contents/MacOS/mscore",
    "/Applications/MuseScore Studio 4.app/Contents/MacOS/mscore",
    "/Applications/MuseScore.app/Contents/MacOS/mscore",
]


class CommandResolutionError(RuntimeError):
    """Raised when an external command cannot be resolved."""

    def __init__(
        self,
        *,
        tool_name: str,
        env_var: str,
        option_name: str,
        candidates: list[str],
        configured_value: str | None = None,
    ) -> None:
        self.tool_name = tool_name
        self.env_var = env_var
        self.option_name = option_name
        self.candidates = candidates
        self.configured_value = configured_value
        super().__init__(self._build_message())

    def _build_message(self) -> str:
        lines = [f"{self.tool_name} コマンドが見つかりません。"]
        if self.configured_value:
            lines.append(f"設定されていた値: {self.configured_value}")
        if self.candidates:
            lines.append("確認した候補: " + ", ".join(self.candidates))
        lines.extend(
            [
                "環境変数で指定してください:",
                f'  export {self.env_var}="/path/to/{self.tool_name.lower()}"',
                "またはオプションで渡してください:",
                f'  {self.option_name} "/path/to/{self.tool_name.lower()}"',
            ]
        )
        if self.tool_name == "MuseScore":
            lines.extend(
                [
                    "macOSのMuseScore 4では、次のパスになることがあります:",
                    '  export SCORE2LOGIC_MUSESCORE_CMD="/Applications/MuseScore 4.app/Contents/MacOS/mscore"',
                ]
            )
        return "\n".join(lines)


@dataclass
class AppConfig:
    """Runtime configuration for score conversion."""

    workdir: Path = field(default_factory=lambda: Path("work"))
    audiveris_cmd: str | None = None
    musescore_cmd: str | None = None
    keep: bool = False
    verbose: bool = False
    progress: bool = False


def resolve_audiveris_command(explicit_cmd: str | None = None) -> str:
    """Resolve the Audiveris command by CLI option, env var, then PATH."""

    return _resolve_command(
        tool_name="Audiveris",
        explicit_cmd=explicit_cmd,
        env_var=AUDIVERIS_ENV,
        option_name="--audiveris-cmd",
        path_candidates=["audiveris"],
        app_candidates=AUDIVERIS_MACOS_CANDIDATES,
    )


def resolve_musescore_command(explicit_cmd: str | None = None) -> str:
    """Resolve the MuseScore command by CLI option, env var, then PATH."""

    return _resolve_command(
        tool_name="MuseScore",
        explicit_cmd=explicit_cmd,
        env_var=MUSESCORE_ENV,
        option_name="--musescore-cmd",
        path_candidates=["mscore", "musescore"],
        app_candidates=MUSESCORE_MACOS_CANDIDATES,
    )


def _resolve_command(
    *,
    tool_name: str,
    explicit_cmd: str | None,
    env_var: str,
    option_name: str,
    path_candidates: list[str],
    app_candidates: list[str],
) -> str:
    configured_value = _clean_command_value(explicit_cmd)
    if configured_value is not None:
        resolved = _resolve_configured_command(configured_value)
        if resolved is not None:
            return resolved
        raise CommandResolutionError(
            tool_name=tool_name,
            env_var=env_var,
            option_name=option_name,
            candidates=[*path_candidates, *app_candidates],
            configured_value=configured_value,
        )

    env_value = _clean_command_value(os.environ.get(env_var))
    if env_value is not None:
        resolved = _resolve_configured_command(env_value)
        if resolved is not None:
            return resolved
        raise CommandResolutionError(
            tool_name=tool_name,
            env_var=env_var,
            option_name=option_name,
            candidates=[*path_candidates, *app_candidates],
            configured_value=env_value,
        )

    for candidate in path_candidates:
        found = shutil.which(candidate)
        if found:
            return found

    for candidate in app_candidates:
        resolved = _resolve_configured_command(candidate)
        if resolved is not None:
            return resolved

    raise CommandResolutionError(
        tool_name=tool_name,
        env_var=env_var,
        option_name=option_name,
        candidates=[*path_candidates, *app_candidates],
    )


def _clean_command_value(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _resolve_configured_command(value: str) -> str | None:
    if _looks_like_path(value):
        path = Path(value).expanduser()
        if path.exists() and os.access(path, os.X_OK):
            return str(path)
        return None

    return shutil.which(value)


def _looks_like_path(value: str) -> bool:
    return "/" in value or "\\" in value or value.startswith(".") or value.startswith("~")
