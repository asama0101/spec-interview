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
   - `INFO:` の行は、現在の版と最新版の確認結果なので、そのまま伝える。新しい版があると出たときは、更新のコマンドも伝える（自分では実行しない）。
   - `OK:` の行があるときは、「そろっています」と伝える。
   - `NG:` の行があるときは、1 行ずつ伝える。直し方は、README の「困ったとき」で、`NG:` の文言と同じ見出しの節を案内する。自分で登録や削除はしない。
     - `NG: Python 3.8 以上が必要です。`
     - `NG: claude コマンドが見つかりません`
     - `NG: Playwright MCP を確認できません`
     - `NG: Playwright MCP に --allow-unrestricted-file-access が付いていません`
3. コマンドが 30 秒以上応答しないときは、`claude mcp get playwright` が MCP サーバーへ接続できていない可能性を伝えて終わる。
