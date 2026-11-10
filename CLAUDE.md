# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 概要

Claude Code 用プラグイン。質問をブラウザのフォームで出し、回答を重ねて SPEC（Markdown 1 ファイル）にまとめる。Windows 11 専用。利用者向けの説明は `README.md` にある（README に開発者向けの案内は書かない。テストが検査している）。

## コマンド

開発用の依存は `requirements-dev.txt`。`.venv/` は Git 管理外なので、手順は `docs/development.md` の「準備」を見る。

```bash
.venv/Scripts/python -m pytest                                  # 全テスト
.venv/Scripts/python -m pytest tests/test_skill.py -k "version" # 1 件だけ
.venv/Scripts/python -m ruff check .                            # lint（ルールは pyproject.toml）
python plugins/spec-interview/scripts/spec_interview.py doctor   # 環境の点検
```

`test_claude_plugin_validateが通る` は `claude plugin validate --strict` を実行する（`claude` がなければ skip）。

## 構成

実装は `plugins/spec-interview/` の 3 つが組になっている。

- `skills/spec-interview/SKILL.md`: 質疑の手順そのもの。Claude が読んで実行する。コードではなく手順書が本体
- `scripts/spec_interview.py`: SKILL.md から呼ぶ補助スクリプト（標準ライブラリのみ、Python 3.8 以上）。サブコマンドは先頭の docstring が正本
- `scripts/spec_interview_template.html`: `render` が質問 JSON を `__DATA__` に埋め込んで、1 ファイルの HTML にする

実行時の流れ: Claude が質問 JSON を書く → `render` が HTML を作る → Playwright MCP が `file://` で開く → 送信すると `window.__submitted` と `window.__answersMd` が立つ → Claude が `browser_evaluate` で待って回答を読む。Playwright MCP はプラグインに同梱せず、利用者が別に登録する。

作業用ファイルは OS の一時フォルダ（`init`）、最終成果の SPEC は起動フォルダの `docs/spec-interview/specs/`（`spec-path`）に置く。

## 守ること

- `tests/test_skill.py` は SKILL.md・README・メタ情報の規約を検査する。SKILL.md や README を直したら、テストを先に流す。たとえば次を検査している。
  - SKILL.md の 1 行の長さ、`allowed-tools` をサブコマンドごとに絞ること
  - 絶対パスや `CLAUDE_SKILL_DIR` を使わないこと
  - README の章の順番（機能 → 前提条件 → 導入方法 → 使い方 → 設定 → 困ったとき → ライセンス・連絡先）
- 版は `plugins/spec-interview/.claude-plugin/plugin.json` の `version` と、`spec_interview.py` の `__version__` の 2 か所にある。必ず一致させる。
- `spec_interview.py` の `embed()` は、HTML の `<script>` に JSON を埋め込むために `<` などを無害化している。テンプレートへの埋め込みはこれを通す。
- SKILL.md の「ルール」節は、mattpocock/skills の grilling の翻案。出典の版は `NOTICE` に固定してあり、テストが最新版かを確かめる（ネットワークが要る）。
- 開発者向けの文書は `docs/development.md`（コマンド・しくみ・版の上げ方）。README には開発者向けの案内を書かない。
- `docs/superpowers/` は `.gitignore` で Git 管理外（作業メモの置き場）。
- このリポジトリで spec-interview を試すと、SPEC が `docs/spec-interview/specs/` にでき、`docs/` が管理対象なのでコミット対象になる。コミットしたくないときは、試す前に `.gitignore` へ加える。

## docs の更新方法

`docs/development.md` を形骸化させないための決まり。

- コードや手順を変える PR で、同じ PR のうちに `docs/development.md` を直す。あとで直す、は認めない。
- 次の変更をしたら、右の節を見直す。

  | 変えたもの | 見直す節 |
  | --- | --- |
  | `requirements-dev.txt`、`pyproject.toml`、テストの実行方法 | 準備、確認のコマンド |
  | `scripts/` の構成、サブコマンド、実行の流れ | しくみ |
  | SKILL.md・README の規約、テストの検査内容 | 直すときの決まり |
  | 版の置き場、リリースの手順 | 版を上げる |

- 件数・行番号・関数や引数の一覧は書かない。コードや docstring が正本なので、文書に写すと古くなる。
- コマンドは、書く前に実際に実行して通ることを確かめる。
- PR を出す前に、`docs/development.md` に書いたファイル名とコマンドが、いまも実在し通ることを確かめる。
- この CLAUDE.md の「構成」「守ること」と `docs/development.md` が食い違ったら、同じ PR で両方をそろえる。
