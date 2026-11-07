# 使い方

## 前提

- フックとカスタムサブエージェントに対応した Codex CLI、Git、Python 3.10 以上。
- Linux / macOS は Bash、Windows は Git for Windows の Git Bash を用意する。Windows の Codex CLI は PowerShell 環境で起動でき、フックは PATH 上の Git Bash を呼び出す。
- ここではプロジェクトの Git リポジトリのルートから Codex とランチャを起動する。
- 同じユーザ環境または対象プロジェクトで、同名の SDLC スキルや `scripts/sdlc` を使う別版との同居は避ける。

## 1. インストール

配布元を clone し、依存を入れる。

```bash
git clone https://github.com/yamasuki-/sdlc-workflow-codex-light.git
cd sdlc-workflow-codex-light
python3 -m pip install -r requirements.txt
```

作業対象は別の Git リポジトリ。新規なら対象ディレクトリを作り `git init` を実行しておく。
次の A / B のいずれかを選ぶ。先に配置先を確認するときは同じコマンドに `--dry-run` を付ける。

| 配置 | コマンド | 本体とフック | スキル |
|---|---|---|---|
| A. プロジェクト配置 | `python3 install.py --project /path/to/project` | 対象の `.codex/` | 対象の `.agents/skills/` |
| B. ユーザ配置 | `python3 install.py --user` | `~/.codex/`（`CODEX_HOME` があればその配下） | `~/.agents/skills/` |

A はチームでバージョンをそろえる場合、B は複数のプロジェクトで同じ本体を使う場合に向きます。
Codex の設定は既存の `hooks.json` に SDLC のハンドラを追加します。
CLI とテンプレートはプロジェクト配置を優先します。Codex は同名スキルを併合せず、ユーザ配置とプロジェクト配置の両方があると一覧に同名が出るため、利用する配置を一つ選んでください。

## 2. 人の端末で初期化

A の場合は対象のリポジトリで以下を実行する。

```bash
cd /path/to/project
bash .codex/sdlc/bin/py .codex/sdlc/bin/sdlc init
```

B の場合は次を実行する。

```bash
cd /path/to/project
sdlc_home="${CODEX_HOME:-$HOME/.codex}/sdlc"
bash "$sdlc_home/bin/py" "$sdlc_home/bin/sdlc" init
```

この処理で `scripts/sdlc`、`scripts/approve`（Windows 用 `.cmd` を含む）、`state/`、`docs/`、`project.yaml` の雛形を作ります。
既存の `AGENTS.md` にルール参照を追記します。次に Codex CLI を起動し、プロジェクト配置ではプロジェクトを信頼したうえで、`/hooks` から SDLC フックの内容を確認して信頼してください。定義を更新した場合も確認します。

Codex プロンプトで **`$sdlc-init`** と入力し、候補から選択します。
言語、ソース・テストの別ディレクトリ、テストコマンドを決めます。設定後に次を確認します。

```bash
scripts/sdlc project check
scripts/sdlc where
scripts/sdlc status
```

### Windows（PowerShell）

インストーラと依存パッケージの導入には `py -3 install.py ...` と `py -3 -m pip install -r requirements.txt` を使えます。
初期化はプロジェクトのルートで実行します。

```powershell
# プロジェクト配置
py -3 .codex/sdlc/bin/sdlc init

# ユーザ配置
$sdlcConfig = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }
py -3 (Join-Path $sdlcConfig 'sdlc/bin/sdlc') init

# 初期化後
.\scripts\sdlc.cmd status
.\scripts\approve.cmd 01
```

承認には対話端末を使います。Git Bash の mintty で端末として認識されない場合は PowerShell かコマンドプロンプトを使います。
`SDLC_PYTHON` で利用する Python、`SDLC_BASH` で検査用コマンドの Bash を指定できます。

## 3. 開始・承認・再開

1. 要求の原本を `input/` に置く。試す場合は [examples/sample-requirements.md](examples/sample-requirements.md) をコピーできる。
2. Codex に `$sdlc` を指定する。工程 01 の要求・SPEC・TC とレビュー結果がそろうと承認待ちになる。
3. 仕様と確認方法を読み、別の対話端末で `scripts/approve 01` を実行する。承認・条件付き承認・差戻しを選ぶ。承認時の SHA-256 は `state/gates/` に記録される。
4. Codex で `$sdlc` を再実行する。02 設計と 03 実装は既定で機械チェックと AI レビューを通過すると進む。追加の承認が必要なら `project.yaml` の `gates` に工程 ID（例 `02-design`）を設定する。
5. 04 受入確認で `docs/04-acceptance/results.md` に人が結果を記入する。選択肢は `OK`、`NG`、`保留`、`対象外`。NG の場合は現象、対象外の場合は理由をメモに記録する。
6. `$sdlc` で再開する。NG は不具合として扱い、該当 TC を修正後に再確認する。受入の進捗は `scripts/sdlc testitems report` で確認できる。

Excel で手動確認結果を記入する場合も、出力と取り込みは人の端末で行う。

```bash
scripts/sdlc testitems export
# docs/04-acceptance/results.xlsx を開き、結果・メモを記入
scripts/sdlc testitems import docs/04-acceptance/results.xlsx
```

テスト種別が「自動」「両方」の TC は結合テストに対応させ、テストコードに `trace: TC-xxx` を書きます。
`scripts/sdlc trace matrix` で追跡関係、`scripts/sdlc gate status` で承認状態、`scripts/sdlc -h` でコマンド一覧を確認できます。

## 4. 不具合・仕様変更・セキュリティ

| 目的 | Codex プロンプトの例 | 処理 |
|---|---|---|
| 承認した仕様との不一致を修正 | `$defect DEF-001` または `$defect ログイン時に画面が固まる` | 再現と原因特定、対象工程から修正、再テスト |
| 振る舞いを変更 | `$change CR-001` または `$change 貸出上限を4冊にする` | SPEC と TC の差分を作成し 01 を再承認 |
| セキュリティレビュー | `$sdlc-security all`、`$sdlc-security since v1.0.0`、`$sdlc-security src/auth` | `security.tools` と専門レビュアーで検査し、`docs/security/` に記録 |

変更要求と不具合の範囲を確認するには `scripts/sdlc trace impact <ID...>` を使用します。
セキュリティレビューの所見は、人が起票対象を決めます。

## フックと承認の適用範囲

- `PreToolUse` は Codex の `apply_patch` とシェルを検査し、承認記録の直接変更、受入結果の直接変更、承認コマンドの実行、無効なゲートをまたぐ成果物編集を検出して拒否します。
- 各工程スキルは編集や委任の前に `scripts/sdlc gate check <工程ID>` を実行します。工程完了時も CLI が前工程の承認、機械チェックとレビューの条件を確認します。
- シェルの検出はコマンド文字列に対する判定です。間接的なファイル操作やフックを経由しないツールを網羅できません。承認済み成果物の変更は CLI のハッシュ照合でも検出します。承認記録と受入結果は Git の履歴で確認できます。
- 信頼前・無効化時・フック未対応の実行環境では、フックによる拒否を利用できません。この手順はフックを有効化できるローカル Codex CLI を対象としています。
- 作成者と別コンテキストでのレビューを行うため、カスタムサブエージェントが利用できることを確認してください。

## 5. 更新、設定変更、アンインストール

- 更新は同じ配置指定で `install.py` を再実行。インストール後に編集されたファイルは保持され、`--force` で置き換えできます。
- 削除は同じ配置指定に `--uninstall` を追加。初期化で作成した成果物や `AGENTS.md` のルール参照はプロジェクトに残ります。
- テンプレートやチェックリストの実体は `scripts/sdlc path templates/spec.md` などで確認できます。プロジェクト固有の方針は `rules/`、機械チェックは `project.yaml` の `checks` に置きます。
- 本体を保守するときは、人の端末で変更するか、`SDLC_MAINTENANCE=1 codex` でセッションを起動します。承認記録と受入結果のガードは保守時も有効です。

| 状況 | 確認する場所 |
|---|---|
| スキルが見つからない | `.agents/skills/` の配置、Codex の作業ディレクトリ。必要なら再起動 |
| フックが動かない | Codex の `/hooks`、プロジェクトの信頼、Git Bash と Python の PATH |
| 承認後に進めない | `scripts/sdlc gate status`。ハッシュ不一致なら変更内容を確認し、仕様の変更は `$change` で再承認 |
| 03 が完了しない | `scripts/sdlc check` と `scripts/sdlc trace check`。テストコマンドと TC トレースを確認 |
| Python の依存が見つからない | `scripts/sdlc where` で選択される Python を確認し、その Python に依存を導入 |
