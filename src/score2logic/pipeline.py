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
from score2logic.utils.files import (
    changed_since_snapshot,
    ensure_directory,
    ensure_existing_file,
    ensure_parent_directory,
    ensure_supported_input,
    find_musicxml_files,
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


@dataclass(frozen=True)
class ConversionResult:
    input_path: Path
    output_midi_path: Path
    workdir: Path
    log_path: Path
    musicxml_candidates: list[Path]
    selected_musicxml: Path
    audiveris_cmd: str
    musescore_cmd: str
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

    audiveris_cmd = resolve_audiveris_command(config.audiveris_cmd)
    musescore_cmd = resolve_musescore_command(config.musescore_cmd)

    before_candidates = find_musicxml_files(workdir)
    before_snapshot = snapshot_mtimes(before_candidates)

    after_candidates = run_audiveris(
        input_path=input_file,
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
        cleaned_files = remove_files(generated_candidates)

    return ConversionResult(
        input_path=input_file,
        output_midi_path=generated_midi,
        workdir=workdir,
        log_path=log_path,
        musicxml_candidates=candidates_to_consider,
        selected_musicxml=selected_musicxml,
        audiveris_cmd=audiveris_cmd,
        musescore_cmd=musescore_cmd,
        cleaned_files=cleaned_files,
    )
