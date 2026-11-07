# sdlc-workflow-codex-light

Codex CLI 用の軽量 SDLC ワークフロー本体の開発リポジトリです。移植元の `yamasuki-/sdlc-workflow-light` は参照用です。

- 既定の人間ゲートは工程 01。要件・振る舞い仕様とテスト項目の承認を一緒に行う。
- 設計と実装は機械チェックと独立したレビューで進める。結合テストを中心にし、単体テストは必要な箇所に絞る。
- 受入結果の入力と承認は利用者が自身の端末で行う。
- ワークフロー本体は `.codex/sdlc/`、フックは `.codex/hooks.json` と `.codex/hooks/sdlc/`、スキルは `.agents/skills/` にある。
- フック定義の変更時はインストーラとの一致を保ち、`python -m unittest discover -s tests -v` を実行する。
- 利用者に影響する変更は `README.md` と `USAGE.md` に反映する。
