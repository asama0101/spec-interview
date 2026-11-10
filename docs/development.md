# 開発者向けガイド

spec-interview を直すときの手引きです。使い方は [README](../README.md) を見てください。

## 準備

Python 3.8 以上と、Windows 11 が要ります。開発用の依存は `requirements-dev.txt` にあります（pytest と ruff）。

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt
```

## 確認のコマンド

```bash
.venv/Scripts/python -m pytest                                  # 全テスト
.venv/Scripts/python -m pytest tests/test_skill.py -k "version" # 名前に version を含むテストだけ
.venv/Scripts/python -m ruff check .                            # lint
python plugins/spec-interview/scripts/spec_interview.py doctor  # 動作環境の点検
```

- `claude` コマンドがあると、`claude plugin validate --strict` を走らせるテストも動きます。なければ skip されます。
- 出典の版を確かめるテスト（`NOTICE` の固定コミット）はネットワークを使います。

## しくみ

実装は `plugins/spec-interview/` の 3 つが組になっています。

| ファイル | 役割 |
| --- | --- |
| `skills/spec-interview/SKILL.md` | 質疑の手順書です。Claude が読んで実行します。コードではなく、これが本体です |
| `scripts/spec_interview.py` | SKILL.md から呼ぶ補助スクリプトです。標準ライブラリだけで動きます |
| `scripts/spec_interview_template.html` | 質問 JSON を埋め込んで、1 ファイルの HTML にするテンプレートです |

スクリプトのサブコマンドと JSON の形式は、`spec_interview.py` の先頭の docstring が正本です。

実行時の流れは次のとおりです。

1. Claude が質問 JSON を書きます。
2. `render` が、テンプレートの `__DATA__` に JSON を埋め込んで HTML を作ります。
3. Playwright MCP が `file://` で HTML を開きます。
4. 利用者が「送信」を押すと、ページが `window.__submitted` と `window.__answersMd` を立てます。
5. Claude が `browser_evaluate` で送信を待ち、回答を読みます。

作業用ファイルは OS の一時フォルダに置きます（`init`）。最終成果の SPEC は、Claude Code を起動したフォルダの `docs/spec-interview/specs/` に置きます（`spec-path`）。Playwright MCP はプラグインに同梱せず、利用者が別に登録します。

## 直すときの決まり

`tests/test_skill.py` が、SKILL.md・README・メタ情報の規約を検査します。SKILL.md か README を直したら、先にテストを流してください。

- HTML に JSON を埋め込むときは `embed()` を通します。`<` などを無害化して、`<script>` が壊れるのを防ぎます。
- SKILL.md の「ルール」節は、mattpocock/skills の grilling の翻案です。元のライセンス表記は `plugins/spec-interview/NOTICE` にあります。
- README に開発者向けの案内は書きません。この文書に書きます。

## 版を上げる

版は 2 か所にあります。必ず同じ値にします（テストが一致を検査します）。

- `plugins/spec-interview/.claude-plugin/plugin.json` の `version`
- `plugins/spec-interview/scripts/spec_interview.py` の `__version__`

版を上げる変更は、`chore: 版を X.Y.Z に上げる` の件名で、別の PR にします。マージしたあと、タグ `vX.Y.Z` を打って GitHub Release を作ります。

## 変更の流れ

1. `main` から作業ブランチを切ります（`feat/`・`fix/`・`docs/`・`chore/`）。
2. 編集して、テストと lint を流します。
3. Conventional Commits の形式でコミットします（type は英語、説明は日本語）。
4. push して PR を作ります。マージは `--squash` で、利用者が行います。
