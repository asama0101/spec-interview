---
name: doctor
description: grill-form が動くために必要なもの（Python の版、claude コマンド、Playwright MCP の登録）を確認し、足りないものと直し方を知らせる。「grill-form の動作環境を確認して」「doctor」と頼まれたときに使う。フォームで質問を詰める作業には使わない（その場合は grill-form スキルを使う）。
disable-model-invocation: true
allowed-tools: Bash(python "${CLAUDE_PLUGIN_ROOT}/scripts/grill_form.py" doctor) Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/grill_form.py" doctor)
---

# doctor

grill-form の動作環境を確認する。何も変更しない。以下の `python` は、環境に `python` コマンドがなければ `python3` に読み替える。

1. `python "${CLAUDE_PLUGIN_ROOT}/scripts/grill_form.py" doctor` を実行する。1 回だけ実行し、やり直さない。
2. 出力を、日本語で短く知らせる。
   - `OK:` で始まるときは、「そろっています」と伝えて終わる。
   - `NG:` の行があるときは、1 行ずつ伝える。直し方は、README の次の節を案内する。自分で登録や削除はしない。
     - Python の版、`claude` コマンド、Playwright MCP が登録されていない: 「導入方法」の手順 3
     - `--allow-unrestricted-file-access` が付いていない: 「困ったとき」の「すでに `playwright` を登録していて、`claude mcp add` が効かない」
3. コマンドが 30 秒以上応答しないときは、`claude mcp get playwright` が MCP サーバーへ接続できていない可能性を伝えて終わる。
