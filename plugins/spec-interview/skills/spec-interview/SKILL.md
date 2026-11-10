---
name: spec-interview
description: grilling（質問攻めで合意を作る手法）を HTML のフォームで行い、候補選択・コメント・保留で内容を詰めて、最後に SPEC 形式で結果を出す。ユーザーが「HTML で grilling」「spec-interview」と明示したときだけ使う。単に「grill して」と頼まれただけのときは使わない（その場合は grilling スキルを使う）。
disable-model-invocation: true
allowed-tools: Bash(python "${CLAUDE_PLUGIN_ROOT}/scripts/spec_interview.py" init *) Bash(python "${CLAUDE_PLUGIN_ROOT}/scripts/spec_interview.py" spec-path *) Bash(python "${CLAUDE_PLUGIN_ROOT}/scripts/spec_interview.py" render *) Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/spec_interview.py" init *) Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/spec_interview.py" spec-path *) Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/spec_interview.py" render *) Bash(python "${CLAUDE_PLUGIN_ROOT}/scripts/spec_interview.py" doctor) Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/spec_interview.py" doctor)
---

# spec-interview

計画や設計について、ユーザーに質問をラウンド単位で重ねて合意を作る（grilling）。質問と回答は HTML フォームでやり取りし、合意内容を SPEC にまとめる。以下の `python` は、環境に `python` コマンドがなければ `python3` に読み替える。

## ルール
出典: [mattpocock/skills の grilling](https://github.com/mattpocock/skills/tree/main/skills/productivity/grilling)（MIT）を要約・翻案。design tree は、決定ごとにそれに依存する決定が枝分かれする木。frontier は、前提がすべて決着済みで推測なしに今聞ける決定の集まり。

- 決定事項を design tree として扱う。前提が決着済みで今聞ける質問（frontier）を、1ラウンドにまとめて出す。回答を待ってから次へ進む。
- 各質問に推奨案（`recommended` と `reason`）を付ける。選択式にして、トレードオフを `desc` に書く。
- 環境から調べられる事実はサブエージェントに調べさせ、ユーザーには聞かない。決定だけをユーザーに聞く。調査待ちの質問は後のラウンドに回す。
- 回答に `聞き返し` があった質問（状態「要確認」）は、決着していない。次のラウンドで、その質問への説明か補足質問を先頭に出す。聞き返しが残っている間は、frontier が空でも終わらない。
- 文脈が濃い質問は、`body` に背景を書いてよい（簡易 Markdown: 段落・箇条書き・コードブロック・インラインコード。長いと折りたたまれる）。選択肢で絞れない問いは `options` を省略し、自由記述で答えてもらう。
- frontier が空になるまで続ける。決定の木のすべての枝をたどり、黙って仮定したまま残さない。ユーザーが承認するまで、実行（実装・ファイル作成）に移らない。
- 同じラウンドで未決の質問に依存する質問は、そのラウンドに出さず、次のラウンドに回す。
- 質問は、「はい」で推奨案を受け入れられる文言にする。推奨案は、最初の候補に置く。
- 質問 ID（`Q1`, `Q2`…）はセッション通しで一意にする（ラウンドでリセットしない）。

## 手順
1. セッション作成: `python "${CLAUDE_PLUGIN_ROOT}/scripts/spec_interview.py" init --theme "<テーマ>"` を実行する。
   - テーマは ASCII の短い名前にする（Windows の Git Bash 経由の日本語引数は文字化けするため。例: `api-design`）。
   - 出力は 1 行で、OS の一時フォルダの中の作業用フォルダ（以下 `<D>`）。HTML・回答・質問 JSON など、最終成果物以外はすべてここに置く。掃除は OS に任せる。
   - SPEC の保存先（以下 `<S>`）は、手順9で決める。
2. 依頼文を受け取る。起動時の引数・同じメッセージの依頼内容を依頼文とする。足りなければ、ターミナルで質問する（AskUserQuestion か通常の質問）。参考にする資料は、ユーザーがパスで示す。
   - 資料のパスは、前後の引用符（`"`）を外してから、存在するファイルか確認する。存在しない・フォルダのパスは、ユーザーに再入力か対象ファイルの指定を求める。コピーはせず、元のパスのまま読み、パスの一覧は手順8の概要の「入力」に使う。
   - PDF は pdf スキルで文字を読み、図形が重要なときは Read ツールでページを画像として見る。Word は docx スキル、PowerPoint・Excel は pptx・xlsx スキルで文字と図形の構造を読み、図形が重要なときは PDF に書き出して渡すようユーザーに伝える。量が多いときは読み取りをサブエージェントに任せてよい。
3. 質問 JSON を書く。置き場所は `<D>`、ファイル名は `<D>/round-N.json`。形式は `spec_interview.py` の docstring を参照（`title`, `intro`, `questions[]` = `id`, `title`, `body`, `multi`, `options[]`（省略可）= `key`, `label`, `desc`、`recommended[]`, `reason`）。
4. 生成: `python "${CLAUDE_PLUGIN_ROOT}/scripts/spec_interview.py" render --session-dir "<D>" --round <N> --input <json>` → `<D>/round-N.html`。
5. Playwright MCP で `browser_navigate` により `file://` URL を開く。
   - `file:///C:/.../round-N.html` のように、スラッシュ区切りにする。
   - ユーザーに「回答して『送信』を押してください」と伝える。
   - Playwright MCP の `browser_*` ツールが使えない場合は、README の「Playwright MCP を登録する」を案内して止まる（スキルには MCP を同梱していない）。`python "${CLAUDE_PLUGIN_ROOT}/scripts/spec_interview.py" doctor` で不足を確認できる。
6. 送信を自動で待つ（ユーザーに「完了」と入力させない）。`browser_evaluate` で次の関数を実行すると、送信されるか約100秒たつまでブロックして結果を返す。
   `() => new Promise(res => { const t0 = Date.now(); const id = setInterval(() => { if (window.__submitted || Date.now() - t0 > 100000) { clearInterval(id); res({ submitted: !!window.__submitted, md: window.__answersMd }); } }, 500); })`
   - `submitted` が false なら、まだ送信されていない。同じ呼び出しを繰り返す（合計約30分、18回まで）。
   - ユーザーがターミナルに何か入力した場合は、待ちをやめてその内容に従う（「完了」なら即座に下の確認へ進む。やめたい旨なら、そこで終わる）。
   - 上限を超えたら、続行方法をユーザーに聞く。
   - `submitted` が true なら、`md` をそのまま `<D>/round-N.answers.md` に書く（Write）。
   - false（未送信・ウィンドウを閉じた等）なら、書かずに続行方法を聞く。コピーボタンで Markdown を貼ってもらう手もある。
7. 回答を読んで design tree を更新し、次のラウンド（手順3〜）へ。ラウンドごとに新しい HTML を生成する。
   - 保留・聞き返しが残る間は SPEC 案に進まない。frontier が空になり、保留と聞き返しがなくなったら、手順8に進む。保留は、決められない理由を添えて非目標かリスクに書けば通る。
8. 合意内容を SPEC 案にまとめて、最終確認のフォームを開く。
   - SPEC 案は、概要・流れ・受入条件・非目標・リスク・決定ログで構成する。概要の中に「入力」として、依頼文の要約を少し厚めに書き、入力ファイルの元のパス一覧を入れる。
   - フォームを開く前に、クロスレビューをする。この会話の文脈を持たない新しいサブエージェントを 5 体、同時に起動する。互いの結果は見せない。各体に渡すのは、依頼文・参考資料のパス・SPEC 案・その体の観点だけ。依頼文と SPEC 案に秘密情報があれば、マスクしてから渡す。
   - 5 つの観点は次のとおり。
     1. 要件の網羅: 依頼文・参考資料の要求が、SPEC のどこで答えられているか。抜けがないか。
     2. 計画への落とし込み: SPEC に決まっていないことが残らず、writing-plans が計画を作れるか。計画を作るときに推測が要る箇所はないか。
     3. 受入条件と矛盾: 受入条件を第三者が「できた／できていない」と判定できるか。概要・流れ・受入条件・非目標・リスク・決定ログのあいだに矛盾がないか。
     4. シンプルさ: 同じ目的を、より少ない決定・手順・ロジックで達成できないか。依頼にない機能が入っていないか。
     5. リスクと非目標: リスクと非目標に漏れがないか。
   - 指摘のうち、自分だけで直せるものは直す。ユーザーの判断が要るものは、手順3に戻って質問にする。回答後は手順7に戻る。観点どうしで指摘が衝突するとき（特に、シンプルさの削減提案が要件の網羅と衝突するとき）は、自分で選ばず、質問にする。
   - 直したあとの再レビューは 1 回まで。指摘があった観点のレビュアーだけに行う。手順3に戻ったときは、再レビューの回数を 0 に戻す。再レビューのあとに残る指摘は、SPEC のリスクに書く。
   - サブエージェントが使えないときは、同じ 5 つの観点で、自分で SPEC 案を順に読む。
   - クロスレビューの結果は、最終確認のフォームには出さない。
   - `{"title","intro","summary"}` の JSON（`<D>/final-K.json`）で `render --final --round <K>` を実行して `<D>/final-K.html` を開く。K は最終確認の版番号で、1 から始めて修正のたびに 1 増やす（前の版を上書きしない）。
   - 送信の待ち方と回答の記録は手順6と同じ（`<D>/final-K.answers.md` に書く）。
   - 回答が `修正あり` なら、コメントを反映し、K を 1 増やして、この手順8を繰り返す。`承認` なら、手順9へ進む。
9. `承認` なら、SPEC を保存する。
   - まず `python "${CLAUDE_PLUGIN_ROOT}/scripts/spec_interview.py" spec-path --theme "<テーマ>"` を実行し、出力を SPEC の保存先 `<S>`（`<作業フォルダ>/docs/spec-interview/specs/<日付>-<テーマ>-design.md`）とする。`spec-path` は、保存先のフォルダがなければ作る。終了コードが 1 のとき（フォルダを作れない）は、SPEC を別の場所へ書かず、標準エラーの理由を報告して止まる。承認は有効なので、ユーザーが原因を直したあとに、この手順9をやり直す。
   - 作業フォルダはカレントフォルダで決まるので、`cd` せずに実行する。
   - 承認された版の `summary` を、そのまま `<S>` に書く（Write）。別のセッションに SPEC を渡すときは、このファイルを使う。
   - `<S>` のパスを報告する。残るのは SPEC の 1 ファイルだけで、質問と回答の履歴（一時フォルダの `<D>`）は OS の掃除に任せる。

## 回答 Markdown の書式（ページ側が生成する）
```
---
session: <フォルダ名>
round: <N>
---
## Q1
- 選択: A        （複数は「, 」区切り）
- コメント: …    （選択ありは理由・条件の補足、選択なしはコメント自体が回答）
- 聞き返し: …    （Claude への質問。あると状態は「要確認」）
- 状態: 回答 / 保留 / 要確認 / 未回答
```
最終確認は frontmatter が `round` ではなく `final: <K>`（版番号）で、本文は `## 承認` に `判定`（承認 / 修正あり）と `コメント`。

## 注意
- JS の `alert/confirm/prompt` は使わない（ブラウザ操作が止まる）。
- `file://` が開けない場合は、`--allow-unrestricted-file-access` 付きで Playwright MCP が設定されているかを確認する。
