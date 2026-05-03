from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from score2logic import __version__
from score2logic.batch import (
    BatchError,
    BatchPlan,
    BatchResult,
    build_batch_plan,
    run_batch,
)
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
    if args.command == "batch":
        return _batch(args)

    parser.print_help()
    return 2


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
        default=Path("work"),
        help="書き込み可能か確認する作業ディレクトリ。",
    )
    doctor.add_argument("--audiveris-cmd", help="Audiverisの実行パスまたはコマンド名。")
    doctor.add_argument("--musescore-cmd", help="MuseScoreの実行パスまたはコマンド名。")
    doctor.add_argument(
        "--warn-only",
        action="store_true",
        help="失敗項目があっても終了コード0で終了します。",
    )

    convert = subparsers.add_parser(
        "convert",
        help="INPUT_FILEをLogic Proに取り込めるMIDIファイルへ変換します。",
    )
    convert.add_argument("input_file", type=Path, help="入力する楽譜画像またはPDF。")
    convert.add_argument("--out", required=True, type=Path, help="出力MIDIパス。必須です。")
    convert.add_argument(
        "--workdir",
        type=Path,
        default=Path("work"),
        help="ログと中間ファイルを置く作業ディレクトリ。",
    )
    convert.add_argument("--audiveris-cmd", help="Audiverisの実行パスまたはコマンド名。")
    convert.add_argument("--musescore-cmd", help="MuseScoreの実行パスまたはコマンド名。")
    convert.add_argument("--keep", action="store_true", help="中間ファイルを残します。")
    convert.add_argument(
        "--open",
        action="store_true",
        dest="open_finder",
        help="Finderで出力MIDIを表示します。",
    )
    convert.add_argument("--verbose", action="store_true", help="実行コマンドと詳細出力を表示します。")

    batch = subparsers.add_parser(
        "batch",
        help="ディレクトリ内の楽譜ファイルを一括でMIDIへ変換します。",
    )
    batch.add_argument("input_dir", type=Path, help="入力楽譜ファイルを置いたディレクトリ。")
    batch.add_argument("--outdir", required=True, type=Path, help="MIDIファイルの出力ディレクトリ。")
    batch.add_argument(
        "--workdir",
        type=Path,
        default=Path("work"),
        help="ログと中間ファイルを置く作業ディレクトリ。",
    )
    batch.add_argument("--audiveris-cmd", help="Audiverisの実行パスまたはコマンド名。")
    batch.add_argument("--musescore-cmd", help="MuseScoreの実行パスまたはコマンド名。")
    batch.add_argument("--keep", action="store_true", help="中間ファイルを残します。")
    batch.add_argument("--recursive", action="store_true", help="入力ディレクトリを再帰的に探索します。")
    batch.add_argument("--fail-fast", action="store_true", help="最初の失敗で一括変換を停止します。")
    batch.add_argument("--dry-run", action="store_true", help="変換せず、対象ファイルと出力先だけ表示します。")
    batch.add_argument(
        "--open",
        action="store_true",
        dest="open_finder",
        help="完了後にFinderで出力ディレクトリを表示します。",
    )
    batch.add_argument("--verbose", action="store_true", help="実行コマンドと詳細出力を表示します。")

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

    checked_workdir = Path(args.workdir).expanduser().resolve()
    writable, error = check_writable_directory(checked_workdir)
    rows.append(
        (
            "作業ディレクトリの書き込み",
            "OK" if writable else "失敗",
            str(checked_workdir) if writable else (error or "書き込みできません"),
        )
    )

    path_parts = os.environ.get("PATH", "").split(os.pathsep)
    rows.append(("PATHの一部", "情報", "\n".join(path_parts[:6]) if path_parts else "(空)"))

    _print_rows("score2logic doctor", rows)
    has_failures = any(status == "失敗" for _, status, _ in rows)
    if has_failures:
        if args.warn_only:
            print("失敗項目がありますが、--warn-only のため終了コード0で終了します。")
            return 0
        print("失敗項目があります。設定を直してから再実行してください。")
        return 1
    return 0


def _convert(args: argparse.Namespace) -> int:
    config = AppConfig(
        workdir=args.workdir,
        audiveris_cmd=args.audiveris_cmd,
        musescore_cmd=args.musescore_cmd,
        keep=args.keep,
        verbose=args.verbose,
        progress=True,
    )
    log_path = Path(config.workdir).expanduser().resolve() / "score2logic.log"

    try:
        result = convert_score_to_midi(args.input_file, args.out, config)
    except (
        FileValidationError,
        CommandResolutionError,
        CommandExecutionError,
        Score2LogicError,
    ) as exc:
        _print_error(exc, log_path=log_path)
        return 1

    _print_success(result)

    if args.open_finder:
        _reveal_in_finder(result.output_midi_path)

    return 0


def _batch(args: argparse.Namespace) -> int:
    config = AppConfig(
        workdir=args.workdir,
        audiveris_cmd=args.audiveris_cmd,
        musescore_cmd=args.musescore_cmd,
        keep=args.keep,
        verbose=args.verbose,
        progress=True,
    )

    try:
        plan = build_batch_plan(
            input_dir=args.input_dir,
            output_dir=args.outdir,
            workdir=args.workdir,
            recursive=args.recursive,
            create_dirs=not args.dry_run,
        )
    except BatchError as exc:
        _print_error(exc)
        return 1

    if args.dry_run:
        _print_batch_plan(plan)
        return 0

    _print_batch_start(plan)
    try:
        result = run_batch(plan, config, fail_fast=args.fail_fast)
    except CommandResolutionError as exc:
        _print_error(exc)
        return 1

    _print_batch_result(result)

    if args.open_finder:
        _reveal_in_finder(result.plan.output_dir)

    return 0 if result.failure_count == 0 else 1


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


def _print_error(exc: Exception, log_path: Path | None = None) -> None:
    print("score2logic エラー", file=sys.stderr)
    print("==================", file=sys.stderr)
    print(str(exc), file=sys.stderr)
    if log_path is not None:
        print(f"ログ: {log_path}", file=sys.stderr)
        if not log_path.exists():
            print(
                "  まだログは作成されていません。入力確認やコマンド解決の段階で失敗した可能性があります。",
                file=sys.stderr,
            )


def _print_success(result: ConversionResult) -> None:
    print("score2logic")
    print("===========")
    print("変換が完了しました。")
    print(f"入力: {result.input_path}")
    print(f"出力MIDI: {result.output_midi_path}")
    print(f"作業ディレクトリ: {result.workdir}")
    cleaned = set(result.cleaned_files)
    selected_suffix = (
        " (削除済み。残すには --keep を指定してください)"
        if result.selected_musicxml in cleaned
        else ""
    )
    print(f"MusicXML: {result.selected_musicxml}{selected_suffix}")
    print(f"ログ: {result.log_path}")

    if result.prepared_files:
        prepared_suffix = (
            " (削除済み。残すには --keep を指定してください)"
            if result.omr_input_path in cleaned
            else ""
        )
        print(f"OMR入力: {result.omr_input_path}{prepared_suffix}")

    if len(result.musicxml_candidates) > 1:
        print("MusicXML候補が複数見つかりました。最新のファイルを使います:")
        for candidate in result.musicxml_candidates:
            marker = "*" if candidate == result.selected_musicxml else " "
            candidate_suffix = " (削除済み)" if candidate in cleaned else ""
            print(f" {marker} {candidate}{candidate_suffix}")

    if result.cleaned_files:
        print("中間ファイルを削除しました。残したい場合は --keep を指定してください。")


def _print_batch_plan(plan: BatchPlan) -> None:
    print("score2logic batch dry-run")
    print("=========================")
    print(f"入力ディレクトリ: {plan.input_dir}")
    print(f"出力ディレクトリ: {plan.output_dir}")
    print(f"作業ディレクトリ: {plan.workdir}")
    print(f"探索: {'再帰的' if plan.recursive else '直下のみ'}")
    print(f"対象: {len(plan.items)}件")
    for index, item in enumerate(plan.items, start=1):
        print(f"{index}. {item.input_path}")
        print(f"   MIDI: {item.output_midi_path}")
        print(f"   workdir: {item.workdir}")


def _print_batch_start(plan: BatchPlan) -> None:
    print("score2logic batch")
    print("=================")
    print(f"入力ディレクトリ: {plan.input_dir}")
    print(f"出力ディレクトリ: {plan.output_dir}")
    print(f"作業ディレクトリ: {plan.workdir}")
    print(f"対象: {len(plan.items)}件")


def _print_batch_result(result: BatchResult) -> None:
    print("一括変換サマリ")
    print("==============")
    print(f"対象: {len(result.plan.items)}件")
    print(f"実行: {result.attempted_count}件")
    print(f"成功: {result.success_count}件")
    print(f"失敗: {result.failure_count}件")

    if result.success_count:
        print("成功:")
        for item in result.items:
            if item.succeeded:
                print(f"  OK {item.plan_item.input_path} -> {item.plan_item.output_midi_path}")

    if result.failure_count:
        print("失敗:")
        for item in result.items:
            if not item.succeeded:
                print(f"  NG {item.plan_item.input_path} -> {item.plan_item.output_midi_path}")
                print(f"     エラー: {_first_error_line(item.error)}")
                print(f"     ログ: {item.log_path}")


def _first_error_line(exc: Exception | None) -> str:
    if exc is None:
        return "(不明)"
    message = str(exc).strip()
    if not message:
        return exc.__class__.__name__
    return message.splitlines()[0]


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
