# score2logic

score2logic は、Mac上で楽譜画像またはPDFを読み込み、Logic Proに取り込めるMIDIファイルを生成するCLIツールです。

MVPでは、独自OMRエンジンもローカルLLMも使いません。処理は次の外部ツールに委譲します。

1. 楽譜画像/PDFからMusicXMLへの変換: Audiveris
2. MusicXMLからMIDIへの変換: MuseScore CLI
3. MIDIの読み込み・編集: Logic Pro

このMVPの価値は、楽譜認識を完璧にすることではありません。価値は、楽譜ファイルからLogic Proで編集できる `.mid` を最短で作ることです。

## 対応入力

- `.png`
- `.jpg`
- `.jpeg`
- `.tif`
- `.tiff`
- `.pdf`

PDFはMVPではAudiverisへ直接渡します。完全なPDFページ分割は非対応ですが、将来 `pdf_to_images` のような前処理を追加しやすい構成にしています。

## インストール

Python 3.12以上を使ってください。

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install ".[dev]"
```

CLIが使えることを確認します。

```bash
score2logic --help
```

開発中は editable install も使えます。

```bash
python -m pip install -e ".[dev]"
```

新しめのPythonで editable install の `.pth` 読み込みに問題が出る場合は、通常の `python -m pip install ".[dev]"` を使ってください。

## Audiverisの設定

Audiverisは別途インストールしてください。そのうえで、score2logicから実行できるようにします。

コマンド解決の優先順位は次のとおりです。

1. `--audiveris-cmd`
2. 環境変数 `SCORE2LOGIC_AUDIVERIS_CMD`
3. `PATH` 上の `audiveris`

環境変数で指定する例:

```bash
export SCORE2LOGIC_AUDIVERIS_CMD="/path/to/audiveris"
```

コマンド実行時に直接渡す例:

```bash
score2logic convert input.png --out output.mid --audiveris-cmd "/path/to/audiveris"
```

## MuseScore CLIの設定

MuseScoreも別途インストールしてください。macOSのMuseScore 4では、CLI実行ファイルが次の場所にあることがあります。

```bash
export SCORE2LOGIC_MUSESCORE_CMD="/Applications/MuseScore 4.app/Contents/MacOS/mscore"
```

コマンド解決の優先順位は次のとおりです。

1. `--musescore-cmd`
2. 環境変数 `SCORE2LOGIC_MUSESCORE_CMD`
3. `PATH` 上の `mscore`
4. `PATH` 上の `musescore`

## doctor

環境確認を行います。

```bash
score2logic doctor
```

確認内容:

- Pythonバージョン
- Audiverisコマンドを解決できるか
- MuseScoreコマンドを解決できるか
- 作業ディレクトリに書き込めるか
- `PATH` の一部

外部ツールが見つからない場合は、次に試すべき環境変数やCLIオプションを表示します。

## convert

基本的な使い方:

```bash
score2logic convert input.png --out output.mid
score2logic convert input.pdf --out output.mid
```

中間ファイルと詳細ログを確認したい場合:

```bash
score2logic convert sample.png --out sample.mid --keep --verbose
```

主なオプション:

- `--out PATH`: 出力MIDIパス。必須です。
- `--workdir PATH`: 作業ディレクトリ。省略時は `./score2logic-work` です。
- `--audiveris-cmd PATH`: Audiveris実行コマンド。
- `--musescore-cmd PATH`: MuseScore実行コマンド。
- `--keep`: 生成されたMusicXMLなどの中間ファイルを残します。
- `--open`: 変換後にFinderで出力MIDIを表示します。
- `--verbose`: 実行コマンドと標準出力・標準エラーを表示します。

Audiverisは概ね次の形で実行されます。

```bash
audiveris -batch -export -output WORKDIR -- INPUT_FILE
```

MuseScoreは概ね次の形で実行されます。

```bash
mscore INPUT.musicxml -o OUTPUT.mid
```

Audiverisの出力場所は環境や入力によって変わることがあるため、score2logicは作業ディレクトリ配下から `.musicxml`, `.mxl`, `.xml` を再帰的に探します。複数見つかった場合は候補を表示し、基本的には最新のファイルを使います。

## Logic Proへの取り込み

1. score2logicで `.mid` を生成します。
2. Logic Proを開きます。
3. 生成された `.mid` をトラック領域へドラッグ&ドロップします。
4. 必要に応じて音源、テンポ、クオンタイズを調整します。

## よくあるエラー

### 入力ファイルが見つからない

パスを確認してください。

```bash
score2logic convert /path/to/input.png --out output.mid
```

### 未対応の拡張子

対応している拡張子は `.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`, `.pdf` です。

### Audiverisコマンドが見つからない

環境変数で指定してください。

```bash
export SCORE2LOGIC_AUDIVERIS_CMD="/path/to/audiveris"
```

またはオプションで渡してください。

```bash
--audiveris-cmd "/path/to/audiveris"
```

### MuseScoreコマンドが見つからない

環境変数で指定してください。

```bash
export SCORE2LOGIC_MUSESCORE_CMD="/Applications/MuseScore 4.app/Contents/MacOS/mscore"
```

またはオプションで渡してください。

```bash
--musescore-cmd "/path/to/mscore"
```

### MusicXMLが生成されない

まず詳細ログと中間ファイルを残して実行してください。

```bash
score2logic convert input.png --out output.mid --keep --verbose
```

その後、作業ディレクトリを確認します。

```bash
open score2logic-work
```

低解像度のスキャン、傾いた画像、手書き楽譜、複雑なレイアウトではAudiverisの認識に失敗することがあります。

### MuseScore変換に失敗する

生成されたMusicXMLをMuseScoreで直接開いて確認してください。MuseScoreで読み込めない場合は、OMR結果のMusicXMLを修正してからMIDIへ書き出す必要があります。

## MVPでやらないこと

- 独自OMR実装
- ローカルLLM補正
- GUI
- iPhoneアプリ
- 手書き楽譜対応
- 複雑なMusicXML編集
- 高度なMIDIベロシティ調整
- Logic Proプロジェクトファイルの直接生成
- 完全なPDFページ分割
- 複数パートの高度なトラック分離
