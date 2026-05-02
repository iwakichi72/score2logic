from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from score2logic.config import (
    AppConfig,
    resolve_audiveris_command,
    resolve_musescore_command,
)
from score2logic.external.audiveris import run_audiveris
from score2logic.external.musescore import convert_musicxml_to_midi
from score2logic.external.sips import convert_heic_to_png
from score2logic.utils.files import (
    changed_since_snapshot,
    ensure_directory,
    ensure_existing_file,
    ensure_parent_directory,
    ensure_supported_input,
    find_musicxml_files,
    is_heic_input_path,
    remove_files,
    select_latest_file,
    snapshot_mtimes,
)


class Score2LogicError(RuntimeError):
    """Base class for conversion pipeline errors."""


class MusicXMLNotGeneratedError(Score2LogicError):
    def __init__(self, workdir: Path) -> None:
        self.workdir = workdir
        super().__init__(
            "MusicXMLが生成されませんでした。\n"
            f"作業ディレクトリ: {workdir}\n"
            "Audiverisは終了しましたが、新規作成または更新された .musicxml, .mxl, .xml が見つかりませんでした。\n"
            "次を試してください:\n"
            "  score2logic convert input.png --out output.mid --keep --verbose\n"
            "その後、作業ディレクトリとAudiverisログを確認してください。"
        )


class MidiNotGeneratedError(Score2LogicError):
    def __init__(self, output_path: Path) -> None:
        self.output_path = output_path
        super().__init__(
            "MIDIファイルが生成されませんでした。\n"
            f"期待した出力: {output_path}\n"
            "MuseScoreは正常終了しましたが、出力 .mid ファイルが見つかりません。\n"
            "MusicXMLをMuseScoreで手動で開き、MIDIとして書き出せるか確認してください。"
        )


class PreparedInputNotGeneratedError(Score2LogicError):
    def __init__(self, input_path: Path, prepared_path: Path) -> None:
        self.input_path = input_path
        self.prepared_path = prepared_path
        super().__init__(
            "HEIC/HEIF入力のPNG変換に失敗しました。\n"
            f"入力: {input_path}\n"
            f"期待した変換後ファイル: {prepared_path}\n"
            "sipsは正常終了しましたが、変換後PNGが見つかりません。"
        )


@dataclass(frozen=True)
class ConversionResult:
    input_path: Path
    omr_input_path: Path
    output_midi_path: Path
    workdir: Path
    log_path: Path
    musicxml_candidates: list[Path]
    selected_musicxml: Path
    audiveris_cmd: str
    musescore_cmd: str
    prepared_files: list[Path]
    cleaned_files: list[Path]


def convert_score_to_midi(
    input_path: Path | str,
    output_path: Path | str,
    config: AppConfig,
) -> ConversionResult:
    """Convert a score image/PDF to MIDI through Audiveris and MuseScore."""

    input_file = ensure_existing_file(input_path)
    ensure_supported_input(input_file)

    workdir = ensure_directory(config.workdir)
    output_midi = ensure_parent_directory(output_path)
    log_path = workdir / "score2logic.log"
    omr_input_file, prepared_files = prepare_input_for_omr(
        input_file=input_file,
        workdir=workdir,
        verbose=config.verbose,
    )

    audiveris_cmd = resolve_audiveris_command(config.audiveris_cmd)
    musescore_cmd = resolve_musescore_command(config.musescore_cmd)

    before_candidates = find_musicxml_files(workdir)
    before_snapshot = snapshot_mtimes(before_candidates)

    after_candidates = run_audiveris(
        input_path=omr_input_file,
        workdir=workdir,
        audiveris_cmd=audiveris_cmd,
        verbose=config.verbose,
    )

    generated_candidates = changed_since_snapshot(after_candidates, before_snapshot)
    candidates_to_consider = generated_candidates

    if not candidates_to_consider:
        raise MusicXMLNotGeneratedError(workdir)

    selected_musicxml = select_latest_file(candidates_to_consider)

    generated_midi = convert_musicxml_to_midi(
        musicxml_path=selected_musicxml,
        output_midi_path=output_midi,
        musescore_cmd=musescore_cmd,
        verbose=config.verbose,
        log_path=log_path,
    )

    if not generated_midi.is_file():
        raise MidiNotGeneratedError(generated_midi)

    cleaned_files: list[Path] = []
    if not config.keep:
        cleaned_files = remove_files([*generated_candidates, *prepared_files])

    return ConversionResult(
        input_path=input_file,
        omr_input_path=omr_input_file,
        output_midi_path=generated_midi,
        workdir=workdir,
        log_path=log_path,
        musicxml_candidates=candidates_to_consider,
        selected_musicxml=selected_musicxml,
        audiveris_cmd=audiveris_cmd,
        musescore_cmd=musescore_cmd,
        prepared_files=prepared_files,
        cleaned_files=cleaned_files,
    )


def prepare_input_for_omr(
    *,
    input_file: Path,
    workdir: Path,
    verbose: bool,
) -> tuple[Path, list[Path]]:
    """Prepare the input file so Audiveris can consume it."""

    if not is_heic_input_path(input_file):
        return input_file, []

    prepared_path = convert_heic_to_png(
        input_path=input_file,
        workdir=workdir,
        verbose=verbose,
    )
    if not prepared_path.is_file():
        raise PreparedInputNotGeneratedError(input_file, prepared_path)

    return prepared_path, [prepared_path]
