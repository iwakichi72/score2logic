from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from score2logic import __version__
from score2logic.config import (
    AppConfig,
    CommandResolutionError,
    resolve_audiveris_command,
    resolve_musescore_command,
)
from score2logic.external import CommandExecutionError
from score2logic.pipeline import (
    ConversionResult,
    Score2LogicError,
    convert_score_to_midi,
)
from score2logic.utils.files import FileValidationError, check_writable_directory

app = typer.Typer(
    help="楽譜画像またはPDFを、Logic Proに取り込めるMIDIファイルへ変換します。",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"score2logic {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option("--version", callback=_version_callback, help="バージョンを表示して終了します。"),
    ] = False,
) -> None:
    _ = version


@app.command()
def doctor(
    workdir: Annotated[
        Path,
        typer.Option("--workdir", help="書き込み可能か確認する作業ディレクトリ。"),
    ] = Path("score2logic-work"),
    audiveris_cmd: Annotated[
        str | None,
        typer.Option("--audiveris-cmd", help="Audiverisの実行パスまたはコマンド名。"),
    ] = None,
    musescore_cmd: Annotated[
        str | None,
        typer.Option("--musescore-cmd", help="MuseScoreの実行パスまたはコマンド名。"),
    ] = None,
) -> None:
    """ローカル環境の準備状況を確認します。"""

    table = Table(title="score2logic doctor")
    table.add_column("確認項目")
    table.add_column("状態")
    table.add_column("詳細")

    table.add_row(
        "Pythonバージョン",
        "OK" if sys.version_info >= (3, 12) else "注意",
        sys.version.split()[0],
    )

    _add_command_check(
        table=table,
        label="Audiverisコマンド",
        resolver=lambda: resolve_audiveris_command(audiveris_cmd),
    )
    _add_command_check(
        table=table,
        label="MuseScoreコマンド",
        resolver=lambda: resolve_musescore_command(musescore_cmd),
    )

    writable, error = check_writable_directory(workdir)
    table.add_row(
        "作業ディレクトリの書き込み",
        "OK" if writable else "失敗",
        str(Path(workdir).expanduser()) if writable else (error or "書き込みできません"),
    )

    path_parts = os.environ.get("PATH", "").split(os.pathsep)
    preview = "\n".join(path_parts[:6]) if path_parts else "(空)"
    table.add_row("PATHの一部", "情報", preview)

    console.print(table)


@app.command()
def convert(
    input_file: Annotated[
        Path,
        typer.Argument(help="入力する楽譜画像またはPDF。"),
    ],
    output_midi: Annotated[
        Path,
        typer.Option("--out", help="出力MIDIパス。必須です。"),
    ],
    workdir: Annotated[
        Path,
        typer.Option("--workdir", help="ログと中間ファイルを置く作業ディレクトリ。"),
    ] = Path("score2logic-work"),
    audiveris_cmd: Annotated[
        str | None,
        typer.Option("--audiveris-cmd", help="Audiverisの実行パスまたはコマンド名。"),
    ] = None,
    musescore_cmd: Annotated[
        str | None,
        typer.Option("--musescore-cmd", help="MuseScoreの実行パスまたはコマンド名。"),
    ] = None,
    keep: Annotated[
        bool,
        typer.Option("--keep", help="生成されたMusicXMLなどの中間ファイルを残します。"),
    ] = False,
    open_finder: Annotated[
        bool,
        typer.Option("--open", help="変換後にFinderで出力MIDIを表示します。"),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", help="実行コマンドと詳細出力を表示します。"),
    ] = False,
) -> None:
    """INPUT_FILEをLogic Proに取り込めるMIDIファイルへ変換します。"""

    config = AppConfig(
        workdir=workdir,
        audiveris_cmd=audiveris_cmd,
        musescore_cmd=musescore_cmd,
        keep=keep,
        verbose=verbose,
    )

    try:
        result = convert_score_to_midi(input_file, output_midi, config)
    except (
        FileValidationError,
        CommandResolutionError,
        CommandExecutionError,
        Score2LogicError,
    ) as exc:
        _print_error(exc)
        raise typer.Exit(1) from exc

    _print_success(result)

    if open_finder:
        _reveal_in_finder(result.output_midi_path)


def _add_command_check(
    *,
    table: Table,
    label: str,
    resolver,
) -> None:
    try:
        command = resolver()
    except CommandResolutionError as exc:
        table.add_row(label, "失敗", str(exc))
        return
    table.add_row(label, "OK", command)


def _print_error(exc: Exception) -> None:
    console.print(
        Panel(
            str(exc),
            title="score2logic エラー",
            border_style="red",
        )
    )


def _print_success(result: ConversionResult) -> None:
    console.print(
        Panel(
            "\n".join(
                [
                    "変換が完了しました。",
                    f"MIDI: {result.output_midi_path}",
                    f"MusicXML: {result.selected_musicxml}",
                    f"ログ: {result.log_path}",
                ]
            ),
            title="score2logic",
            border_style="green",
        )
    )

    if len(result.musicxml_candidates) > 1:
        console.print("[yellow]MusicXML候補が複数見つかりました。最新のファイルを使います:[/yellow]")
        for candidate in result.musicxml_candidates:
            marker = "*" if candidate == result.selected_musicxml else " "
            console.print(f" {marker} {candidate}")

    if result.cleaned_files:
        console.print(
            "[dim]中間MusicXMLファイルを削除しました。残したい場合は --keep を指定してください。[/dim]"
        )


def _reveal_in_finder(path: Path) -> None:
    if sys.platform != "darwin":
        console.print("[yellow]--open はmacOS Finder向けにのみ実装されています。[/yellow]")
        return
    try:
        subprocess.run(["open", "-R", str(path)], check=False)
    except OSError as exc:
        console.print(f"[yellow]Finderで出力先を表示できませんでした: {exc}[/yellow]")


if __name__ == "__main__":
    app()
