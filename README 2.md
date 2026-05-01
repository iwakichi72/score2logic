# score2logic

score2logic is a macOS-focused CLI tool that converts score images or PDFs into MIDI files that can be imported into Logic Pro.

The MVP intentionally does not implement its own OMR engine and does not use a local LLM. It delegates:

1. Score image/PDF to MusicXML: Audiveris
2. MusicXML to MIDI: MuseScore CLI
3. MIDI editing and playback: Logic Pro

The value of this MVP is not perfect recognition. The goal is the shortest reliable path from a score file to an editable `.mid` file.

## Supported Inputs

- `.png`
- `.jpg`
- `.jpeg`
- `.tif`
- `.tiff`
- `.pdf`

PDF files are passed directly to Audiveris. Full PDF page splitting is intentionally out of scope for the MVP, but the code is structured so a future `pdf_to_images` step can be added before OMR.

## Installation

Use Python 3.12 or newer.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install ".[dev]"
```

Check that the CLI is available:

```bash
score2logic --help
```

For active development, editable install is also useful:

```bash
python -m pip install -e ".[dev]"
```

If an early/new Python version has trouble with editable `.pth` loading, use the regular install command above.

## Audiveris Setup

Install Audiveris separately, then make the command available to score2logic.

Priority order:

1. `--audiveris-cmd`
2. `SCORE2LOGIC_AUDIVERIS_CMD`
3. `audiveris` on `PATH`

Example:

```bash
export SCORE2LOGIC_AUDIVERIS_CMD="/path/to/audiveris"
```

Or pass it per command:

```bash
score2logic convert input.png --out output.mid --audiveris-cmd "/path/to/audiveris"
```

## MuseScore CLI Setup

Install MuseScore separately. On macOS, MuseScore 4 may expose the CLI executable here:

```bash
export SCORE2LOGIC_MUSESCORE_CMD="/Applications/MuseScore 4.app/Contents/MacOS/mscore"
```

Priority order:

1. `--musescore-cmd`
2. `SCORE2LOGIC_MUSESCORE_CMD`
3. `mscore` on `PATH`
4. `musescore` on `PATH`

## Doctor

Run:

```bash
score2logic doctor
```

It checks:

- Python version
- Audiveris command resolution
- MuseScore command resolution
- Work directory writability
- A short preview of `PATH`

Missing external tools are reported with the environment variables or CLI flags to try next.

## Convert

Basic usage:

```bash
score2logic convert input.png --out output.mid
score2logic convert input.pdf --out output.mid
```

Useful debugging run:

```bash
score2logic convert sample.png --out sample.mid --keep --verbose
```

Options:

- `--out PATH`: required MIDI output path
- `--workdir PATH`: working directory, default `./score2logic-work`
- `--audiveris-cmd PATH`: Audiveris executable
- `--musescore-cmd PATH`: MuseScore executable
- `--keep`: keep generated MusicXML files
- `--open`: reveal the output MIDI in Finder after conversion
- `--verbose`: print command lines and captured output

Audiveris is run like:

```bash
audiveris -batch -export -output WORKDIR -- INPUT_FILE
```

MuseScore is run like:

```bash
mscore INPUT.musicxml -o OUTPUT.mid
```

score2logic searches the work directory recursively for `.musicxml`, `.mxl`, and `.xml` files because Audiveris output locations can vary. If multiple MusicXML candidates are found, the newest file is selected and the candidates are shown.

## Logic Pro Import

1. Generate a `.mid` file with score2logic.
2. Open Logic Pro.
3. Drag and drop the generated `.mid` file into the track area.
4. Adjust instrument, tempo, and quantization as needed.

## Common Errors

### Input file does not exist

Check the path:

```bash
score2logic convert /path/to/input.png --out output.mid
```

### Unsupported input extension

Use one of: `.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`, `.pdf`.

### Audiveris command not found

Set it with:

```bash
export SCORE2LOGIC_AUDIVERIS_CMD="/path/to/audiveris"
```

Or pass:

```bash
--audiveris-cmd "/path/to/audiveris"
```

### MuseScore command not found

Set it with:

```bash
export SCORE2LOGIC_MUSESCORE_CMD="/Applications/MuseScore 4.app/Contents/MacOS/mscore"
```

Or pass:

```bash
--musescore-cmd "/path/to/mscore"
```

### MusicXML was not generated

Run with:

```bash
score2logic convert input.png --out output.mid --keep --verbose
```

Then inspect:

```bash
open score2logic-work
```

Audiveris may fail on low-resolution scans, skewed images, handwriting, or complex layouts.

### MuseScore conversion failed

Open the generated MusicXML in MuseScore manually. If MuseScore cannot import it, the OMR output likely needs correction before MIDI export.

## MVP Non-Goals

- Custom OMR implementation
- Local LLM correction
- GUI
- iPhone app
- Handwritten score support
- Complex MusicXML editing
- Advanced MIDI velocity processing
- Direct Logic Pro project generation
- Complete PDF page splitting
- Advanced multi-part track separation
