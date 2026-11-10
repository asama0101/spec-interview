---
name: doctor
description: spec-interview が動くために必要なもの（Python の版、claude コマンド、Playwright MCP の登録）を確認し、足りないものと直し方を知らせる。「spec-interview の動作環境を確認して」「doctor」と頼まれたときに使う。フォームで質問を詰める作業には使わない（その場合は spec-interview スキルを使う）。
disable-model-invocation: true
allowed-tools: Bash(python "${CLAUDE_PLUGIN_ROOT}/scripts/spec_interview.py" doctor) Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/spec_interview.py" doctor)
---

# doctor

spec-interview の動作環境を確認する。何も変更しない。以下の `python` は、環境に `python` コマンドがなければ `python3` に読み替える。

1. `python "${CLAUDE_PLUGIN_ROOT}/scripts/spec_interview.py" doctor` を実行する。1 回だけ実行し、やり直さない。
2. 出力を、日本語で短く知らせる。
   - `[情報]` の行は、現在の版と最新版の確認結果なので、そのまま伝える。新しい版があると出たときは、更新のコマンドも伝える（自分では実行しない）。
   - `[OK]` の行は、一言で済ませる。
   - `[NG]` の行があるときは、1 行ずつ伝える。直し方は、README の「困ったとき」で、`[NG]` の文言と同じ見出しの節を案内する。自分で登録や削除はしない。
     - `[NG] OS`
     - `[NG] 実行環境: Python 3.8 以上が必要です。`
     - `[NG] claude コマンド: 見つかりません`
     - `[NG] Playwright MCP: 確認できません`
     - `[NG] file:// の許可: --allow-unrestricted-file-access が付いていません`
3. コマンドが 30 秒以上応答しないときは、`claude mcp get playwright` が MCP サーバーへ接続できていない可能性を伝えて終わる。
