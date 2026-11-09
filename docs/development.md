# 開発者向けメモ

grill-form の仕組みとテストです。使い方は [README.md](../README.md) を見てください。

## ファイル構成

| ファイル | 内容 |
| --- | --- |
| `README.md` | 利用者向けの説明。リポジトリ直下に 1 つだけ置き、プラグインのフォルダの中には置かない（出典の注記は `plugins/grill-form/NOTICE`） |
| `.claude-plugin/marketplace.json` | マーケットプレイスの定義 |
| `plugins/grill-form/.claude-plugin/plugin.json` | プラグインのメタ（version は `grill_form.py` の `__version__` と一致させる） |
| `plugins/grill-form/skills/grill-form/SKILL.md` | スキルの定義と手順 |
| `plugins/grill-form/scripts/grill_form.py` | 補助スクリプト。サブコマンドは下の表 |
| `plugins/grill-form/scripts/grill_form_template.html` | フォームのテンプレート（単一 HTML、外部リソースなし、`innerHTML` は使わない） |
| `plugins/grill-form/NOTICE` | 取り込んだルールの出典とライセンス |
| `tests/` | pytest のテスト |

### `grill_form.py` のサブコマンド

| サブコマンド | 内容 |
| --- | --- |
| `init --theme T` | OS の一時フォルダの下に `grill-form_<テーマ>_<乱数>` を作り、パスを 1 行で出力する。掃除は OS に任せる |
| `spec-path --theme T` | SPEC の保存先 `<作業フォルダ>/docs/grill-form/specs/<日付>-<テーマ>-design.md` を決め、フォルダを作って出力する（ファイルは作らない）。同名があれば連番を付ける。フォルダを作れなければ終了コード 1 |
| `render` | 質問 JSON（`--round N --input J.json`）、最終確認（`--final`）の HTML を生成する |
| `doctor` | Python のバージョン、`claude`、Playwright MCP の登録を確認する（`claude mcp get` は 30 秒で打ち切る）。何も変更しない。足りないものがあれば終了コード 1 |

## 保存先

作業用のファイルは、OS の一時フォルダに置かれます。

| 種類 | 場所 | 寿命 |
| --- | --- | --- |
| 作業用ファイル（質問 JSON・HTML・回答 Markdown） | 一時フォルダ配下 `grill-form_<テーマ>_<乱数>/` | OS の一時フォルダの掃除に任せる |
| Playwright MCP の記録 | 一時フォルダ配下 `playwright-mcp/` | OS の一時フォルダの掃除に任せる |

## ローカルで試す

インストールせずに、clone したフォルダのプラグインを読み込んで起動します。

```bash
claude --plugin-dir ./plugins/grill-form
```

## テストと検査

プラグインの形式（SKILL.md の frontmatter、絶対パス・相対パスを書いていないこと、`${CLAUDE_PLUGIN_ROOT}` が指すファイルの実在、MCP を同梱していないこと、version の一致、`claude plugin validate`）、`grill_form.py` の各サブコマンド、フォームの HTML の構造を、pytest で検査します。スキル本体（実行時）には依存がありません。テストの依存は `requirements-dev.txt` に固定しています。

```bash
python -m venv <一時フォルダ>/grill-form-venv   # プロジェクトの外に作る
<一時フォルダ>/grill-form-venv/Scripts/python -m pip install -r requirements-dev.txt
<一時フォルダ>/grill-form-venv/Scripts/python -m pytest
<一時フォルダ>/grill-form-venv/Scripts/python -m ruff check .
<一時フォルダ>/grill-form-venv/Scripts/python -m ruff format --check .
```

- フォームの動き（次の質問へ移る動き）は、自動テストの対象外です。ブラウザで目視して確かめてください。
