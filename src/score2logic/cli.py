from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

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


def app(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.version:
        print(f"score2logic {__version__}")
        return 0

    if args.command == "doctor":
        return _doctor(args)
    if args.command == "convert":
        return _convert(args)

    parser.print_help()
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="score2logic",
        description="楽譜画像またはPDFを、Logic Proに取り込めるMIDIファイルへ変換します。",
    )
    parser.add_argument("--version", action="store_true", help="バージョンを表示して終了します。")

    subparsers = parser.add_subparsers(dest="command")

    doctor = subparsers.add_parser("doctor", help="ローカル環境の準備状況を確認します。")
    doctor.add_argument(
        "--workdir",
        type=Path,
        default=Path("score2logic-work"),
        help="書き込み可能か確認する作業ディレクトリ。",
    )
    doctor.add_argument("--audiveris-cmd", help="Audiverisの実行パスまたはコマンド名。")
    doctor.add_argument("--musescore-cmd", help="MuseScoreの実行パスまたはコマンド名。")

    convert = subparsers.add_parser(
        "convert",
        help="INPUT_FILEをLogic Proに取り込めるMIDIファイルへ変換します。",
    )
    convert.add_argument("input_file", type=Path, help="入力する楽譜画像またはPDF。")
    convert.add_argument("--out", required=True, type=Path, help="出力MIDIパス。必須です。")
    convert.add_argument(
        "--workdir",
        type=Path,
        default=Path("score2logic-work"),
        help="ログと中間ファイルを置く作業ディレクトリ。",
    )
    convert.add_argument("--audiveris-cmd", help="Audiverisの実行パスまたはコマンド名。")
    convert.add_argument("--musescore-cmd", help="MuseScoreの実行パスまたはコマンド名。")
    convert.add_argument("--keep", action="store_true", help="中間ファイルを残します。")
    convert.add_argument("--open", action="store_true", dest="open_finder", help="Finderで出力MIDIを表示します。")
    convert.add_argument("--verbose", action="store_true", help="実行コマンドと詳細出力を表示します。")

    return parser


def _doctor(args: argparse.Namespace) -> int:
    rows: list[tuple[str, str, str]] = []
    rows.append(
        (
            "Pythonバージョン",
            "OK" if sys.version_info >= (3, 12) else "注意",
            sys.version.split()[0],
        )
    )
    rows.append(
        _command_check(
            "Audiverisコマンド",
            lambda: resolve_audiveris_command(args.audiveris_cmd),
        )
    )
    rows.append(
        _command_check(
            "MuseScoreコマンド",
            lambda: resolve_musescore_command(args.musescore_cmd),
        )
    )

    sips_path = shutil.which("sips")
    rows.append(
        (
            "HEIC/HEIF前処理",
            "OK" if sips_path else "失敗",
            sips_path or "macOS標準の sips コマンドが見つかりません",
        )
    )

    writable, error = check_writable_directory(args.workdir)
    rows.append(
        (
            "作業ディレクトリの書き込み",
            "OK" if writable else "失敗",
            str(Path(args.workdir).expanduser()) if writable else (error or "書き込みできません"),
        )
    )

    path_parts = os.environ.get("PATH", "").split(os.pathsep)
    rows.append(("PATHの一部", "情報", "\n".join(path_parts[:6]) if path_parts else "(空)"))

    _print_rows("score2logic doctor", rows)
    return 0


def _convert(args: argparse.Namespace) -> int:
    config = AppConfig(
        workdir=args.workdir,
        audiveris_cmd=args.audiveris_cmd,
        musescore_cmd=args.musescore_cmd,
        keep=args.keep,
        verbose=args.verbose,
    )

    try:
        result = convert_score_to_midi(args.input_file, args.out, config)
    except (
        FileValidationError,
        CommandResolutionError,
        CommandExecutionError,
        Score2LogicError,
    ) as exc:
        _print_error(exc)
        return 1

    _print_success(result)

    if args.open_finder:
        _reveal_in_finder(result.output_midi_path)

    return 0


def _command_check(label: str, resolver) -> tuple[str, str, str]:
    try:
        command = resolver()
    except CommandResolutionError as exc:
        return label, "失敗", str(exc)
    return label, "OK", command


def _print_rows(title: str, rows: list[tuple[str, str, str]]) -> None:
    print(title)
    print("=" * len(title))
    for label, status, details in rows:
        print(f"{label}: {status}")
        for line in details.splitlines():
            print(f"  {line}")


def _print_error(exc: Exception) -> None:
    print("score2logic エラー", file=sys.stderr)
    print("==================", file=sys.stderr)
    print(str(exc), file=sys.stderr)


def _print_success(result: ConversionResult) -> None:
    print("score2logic")
    print("===========")
    print("変換が完了しました。")
    print(f"MIDI: {result.output_midi_path}")
    print(f"MusicXML: {result.selected_musicxml}")
    print(f"ログ: {result.log_path}")

    if result.prepared_files:
        print(f"OMR入力: {result.omr_input_path}")

    if len(result.musicxml_candidates) > 1:
        print("MusicXML候補が複数見つかりました。最新のファイルを使います:")
        for candidate in result.musicxml_candidates:
            marker = "*" if candidate == result.selected_musicxml else " "
            print(f" {marker} {candidate}")

    if result.cleaned_files:
        print("中間ファイルを削除しました。残したい場合は --keep を指定してください。")


def _reveal_in_finder(path: Path) -> None:
    if sys.platform != "darwin":
        print("--open はmacOS Finder向けにのみ実装されています。", file=sys.stderr)
        return
    try:
        subprocess.run(["open", "-R", str(path)], check=False)
    except OSError as exc:
        print(f"Finderで出力先を表示できませんでした: {exc}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(app())
