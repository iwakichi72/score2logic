from __future__ import annotations

from score2logic.utils.logging import command_to_string


class CommandExecutionError(RuntimeError):
    """Raised when an external command exits unsuccessfully."""

    def __init__(
        self,
        *,
        tool_name: str,
        command: list[str],
        returncode: int,
        stdout: str,
        stderr: str,
    ) -> None:
        self.tool_name = tool_name
        self.command = command
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        super().__init__(self._build_message())

    def _build_message(self) -> str:
        stderr_text = self.stderr.strip() or "(empty)"
        stdout_text = self.stdout.strip() or "(empty)"
        return "\n".join(
            [
                f"{self.tool_name} の実行に失敗しました。",
                "実行コマンド:",
                f"  {command_to_string(self.command)}",
                f"終了コード: {self.returncode}",
                "stderr:",
                stderr_text,
                "stdout:",
                stdout_text,
                "次に試すこと:",
                "  --keep --verbose を付けて再実行し、中間ファイルとコマンド出力を確認してください。",
            ]
        )
