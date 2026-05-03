from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from score2logic.config import (
    AppConfig,
    resolve_audiveris_command,
    resolve_musescore_command,
)
from score2logic.external import CommandExecutionError
from score2logic.pipeline import ConversionResult, Score2LogicError, convert_score_to_midi
from score2logic.utils.files import (
    FileValidationError,
    ensure_directory,
    is_supported_input_path,
    supported_input_extensions_text,
)


class BatchError(RuntimeError):
    """Base class for batch conversion errors."""


class BatchInputDirectoryError(BatchError):
    def __init__(self, path: Path) -> None:
        self.path = path
        super().__init__(
            "入力ディレクトリが見つかりません。\n"
            f"パス: {path}\n"
            "一括変換したい楽譜ファイルを置いたディレクトリを指定してください。"
        )


class NoBatchInputFilesError(BatchError):
    def __init__(self, path: Path, recursive: bool) -> None:
        self.path = path
        self.recursive = recursive
        mode = "再帰的に" if recursive else "直下から"
        super().__init__(
            "変換対象の入力ファイルが見つかりません。\n"
            f"入力ディレクトリ: {path}\n"
            f"探索範囲: {mode}対応拡張子を探しました。\n"
            f"対応拡張子: {supported_input_extensions_text()}"
        )


@dataclass(frozen=True)
class BatchPlanItem:
    input_path: Path
    output_midi_path: Path
    workdir: Path


@dataclass(frozen=True)
class BatchPlan:
    input_dir: Path
    output_dir: Path
    workdir: Path
    recursive: bool
    items: list[BatchPlanItem]


@dataclass(frozen=True)
class BatchItemResult:
    plan_item: BatchPlanItem
    conversion: ConversionResult | None
    error: Exception | None

    @property
    def succeeded(self) -> bool:
        return self.error is None

    @property
    def log_path(self) -> Path:
        if self.conversion is not None:
            return self.conversion.log_path
        return self.plan_item.workdir / "score2logic.log"


@dataclass(frozen=True)
class BatchResult:
    plan: BatchPlan
    items: list[BatchItemResult]

    @property
    def success_count(self) -> int:
        return sum(1 for item in self.items if item.succeeded)

    @property
    def failure_count(self) -> int:
        return sum(1 for item in self.items if not item.succeeded)

    @property
    def attempted_count(self) -> int:
        return len(self.items)


def discover_batch_inputs(input_dir: Path | str, *, recursive: bool = False) -> list[Path]:
    directory = Path(input_dir).expanduser().resolve()
    if not directory.is_dir():
        raise BatchInputDirectoryError(directory)

    candidates = directory.rglob("*") if recursive else directory.iterdir()
    files = [
        path.resolve()
        for path in candidates
        if path.is_file() and is_supported_input_path(path)
    ]
    return sorted(files, key=lambda path: str(path))


def build_batch_plan(
    *,
    input_dir: Path | str,
    output_dir: Path | str,
    workdir: Path | str,
    recursive: bool = False,
    create_dirs: bool = True,
) -> BatchPlan:
    source_dir = Path(input_dir).expanduser().resolve()
    if not source_dir.is_dir():
        raise BatchInputDirectoryError(source_dir)

    resolved_output_dir = _resolve_directory(output_dir, create=create_dirs)
    resolved_workdir = _resolve_directory(workdir, create=create_dirs)
    inputs = [
        path
        for path in discover_batch_inputs(source_dir, recursive=recursive)
        if not _is_relative_to(path, resolved_output_dir)
        and not _is_relative_to(path, resolved_workdir)
    ]
    if not inputs:
        raise NoBatchInputFilesError(source_dir, recursive)

    used_stems: set[str] = set()
    items: list[BatchPlanItem] = []

    for input_path in inputs:
        stem = _unique_stem(input_path.stem or "input", used_stems)
        items.append(
            BatchPlanItem(
                input_path=input_path,
                output_midi_path=resolved_output_dir / f"{stem}.mid",
                workdir=resolved_workdir / stem,
            )
        )

    return BatchPlan(
        input_dir=source_dir,
        output_dir=resolved_output_dir,
        workdir=resolved_workdir,
        recursive=recursive,
        items=items,
    )


def run_batch(
    plan: BatchPlan,
    config: AppConfig,
    *,
    fail_fast: bool = False,
) -> BatchResult:
    audiveris_cmd = resolve_audiveris_command(config.audiveris_cmd)
    musescore_cmd = resolve_musescore_command(config.musescore_cmd)
    results: list[BatchItemResult] = []

    for item in plan.items:
        item_config = AppConfig(
            workdir=item.workdir,
            audiveris_cmd=audiveris_cmd,
            musescore_cmd=musescore_cmd,
            keep=config.keep,
            verbose=config.verbose,
            progress=config.progress,
        )
        try:
            conversion = convert_score_to_midi(
                item.input_path,
                item.output_midi_path,
                item_config,
            )
        except (
            FileValidationError,
            CommandExecutionError,
            Score2LogicError,
        ) as exc:
            results.append(BatchItemResult(item, conversion=None, error=exc))
            if fail_fast:
                break
        else:
            results.append(BatchItemResult(item, conversion=conversion, error=None))

    return BatchResult(plan=plan, items=results)


def _unique_stem(stem: str, used_stems: set[str]) -> str:
    candidate = stem
    index = 2
    while candidate in used_stems:
        candidate = f"{stem}-{index}"
        index += 1
    used_stems.add(candidate)
    return candidate


def _resolve_directory(path: Path | str, *, create: bool) -> Path:
    if create:
        return ensure_directory(path)
    return Path(path).expanduser().resolve()


def _is_relative_to(path: Path, directory: Path) -> bool:
    try:
        path.relative_to(directory)
    except ValueError:
        return False
    return True
