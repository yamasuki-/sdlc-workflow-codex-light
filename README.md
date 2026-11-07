# sdlc-workflow-codex-light

Codex CLI で動く軽量版のソフトウェア開発ワークフローです。
[Claude Code 版 sdlc-workflow-light](https://github.com/yamasuki-/sdlc-workflow-light/tree/47f23be719c4622a5c949ac356a5942771892cf8) を移植元とし、同じ4工程と成果物の形式を使います。

要件・振る舞い仕様とテスト項目をまとめて人が承認します。設計・実装は機械チェックと独立した AI レビューで進み、最後に人が手動テストの結果を記録します。自動テストは結合テストを中心にし、単体テストは必要なロジックに絞ります。

| 工程 | 主な成果物 | 既定の完了条件 |
|---|---|---|
| 01 要件・仕様 | 要求・非機能要件、振る舞い仕様（SPEC）、テスト項目（TC） | 機械チェック、レビュー、人の承認 |
| 02 設計 | 構成、インターフェース、データ、テスト方針 | 機械チェックとレビュー |
| 03 実装 | コード、結合テスト、手動確認手順 | 自動テスト、TC のトレース、レビュー |
| 04 受入確認 | Markdown の結果シート（Excel 入出力可）、結果の集計 | 自動テストと、人による手動 TC の確認 |

`project.yaml` の `gates` に工程 ID を追加すると、その工程にも人の承認を求められます。
承認時の成果物を SHA-256 で記録し、承認後の変更を検知します。

## 始め方

フックとカスタムサブエージェントに対応する Codex CLI、Git、Bash、Python 3.10 以上が必要です。Windows は Git for Windows の Git Bash も使います。

1. [USAGE.md](USAGE.md) に従い、作業対象の Git リポジトリにインストール・初期化する。
2. Codex CLI でプロジェクトとフックを確認し、`$sdlc-init` で `project.yaml` を設定する。
3. `input/` に原本（Markdown、Excel、Word、PowerPoint、PDF）を置き、`$sdlc` を実行する。
4. 工程 01 の承認待ちになったら、別の対話端末で `scripts/approve 01` を実行する。
5. `$sdlc` で再開し、受入確認で `docs/04-acceptance/results.md` を記入してから再度 `$sdlc` を実行する。

| Codex で指定するスキル | 用途 |
|---|---|
| `$sdlc` | 状態に応じて開始・再開 |
| `$sdlc-init` | プロジェクト設定 |
| `$defect` | 承認済みの仕様との不一致を調査・修正し、対象 TC を再確認 |
| `$change` | 振る舞いを変更し、仕様と TC の差分を再承認 |
| `$sdlc-security` | 全体・差分・パスを指定して随時レビュー |

## 構成

| パス | 内容 |
|---|---|
| `.agents/skills/` | 開始・初期化、4工程、不具合・変更要求・セキュリティレビュー |
| `.codex/agents/` | 要求分析・設計実装・テスト・独立レビュー・セキュリティレビューの役割 |
| `.codex/hooks.json`、`.codex/hooks/sdlc/` | セッション開始時の状態表示、書き込み・シェル操作のガード |
| `.codex/sdlc/` | 状態管理 CLI、ライブラリ、工程フロー、テンプレート、チェックリスト |
| `AGENTS.md` | 開発時の指示。導入先には SDLC 共通ルールへの参照が追加される |
| `examples/`、`tests/` | サンプル要求と自己テスト |

フックは信頼済みのローカル Codex CLI で利用できます。対象ツールとシェルの検出には限界があるため、運用上の制約を [USAGE.md](USAGE.md#フックと承認の適用範囲) に記載しています。

自己テストは依存パッケージを導入後、`python -m unittest discover -s tests -v` で実行できます。
