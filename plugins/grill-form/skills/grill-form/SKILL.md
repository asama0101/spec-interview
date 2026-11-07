---
name: grill-form
description: grilling（質問攻めで合意を作る手法）を HTML のフォームで行い、候補選択・コメント・保留で内容を詰めて、最後に SPEC 形式で結果を出す。ユーザーが「HTML で grilling」「grill-form」と明示したときだけ使う。単に「grill して」と頼まれただけのときは使わない（その場合は grilling スキルを使う）。
disable-model-invocation: true
allowed-tools: Bash(python "${CLAUDE_PLUGIN_ROOT}/scripts/grill_form.py" init *) Bash(python "${CLAUDE_PLUGIN_ROOT}/scripts/grill_form.py" spec-path *) Bash(python "${CLAUDE_PLUGIN_ROOT}/scripts/grill_form.py" render *) Bash(python "${CLAUDE_PLUGIN_ROOT}/scripts/grill_form.py" cleanup *) Bash(python "${CLAUDE_PLUGIN_ROOT}/scripts/grill_form.py" list *) Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/grill_form.py" init *) Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/grill_form.py" spec-path *) Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/grill_form.py" render *) Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/grill_form.py" cleanup *) Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/grill_form.py" list *) Bash(python "${CLAUDE_PLUGIN_ROOT}/scripts/grill_form.py" doctor) Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/grill_form.py" doctor)
---

# grill-form

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
0. 未完了セッションの確認（起動時に毎回行う）: `python "${CLAUDE_PLUGIN_ROOT}/scripts/grill_form.py" list --data "${CLAUDE_PLUGIN_DATA}"` を実行する。14 日より古いセッションは、このとき先に削除される。
   - 出力は 1 行に 1 セッションで、フォルダ名・テーマ・更新日時・最新のファイル名をタブで区切る（更新日時の新しい順）。出力が空なら、未完了のセッションはない。手順1へ進む。
   - 出力があるときは、AskUserQuestion の選択肢で聞く。「新規」と、新しい 3 件までのセッションの「再開（テーマ・更新日時・最新のファイル名）」を新しい順に出す（選択肢は 4 つまで）。それより古いセッションは「その他」にフォルダ名を入力して選んでもらう。
   - 「新規」なら、手順1へ進む。
   - 「再開」なら、そのセッションのフォルダ（以下 `<D>`）の中のファイルを読み、下の表で続きの手順を決めて、そこから始める。テーマは `<D>/session.json` の `theme` を使い、SPEC の保存先は手順10の `spec-path --theme` で決める。質問 ID は通しで一意なので、既存の `round-*.json` の最大の ID の次から付ける。

     表は新しい段階から順に照らし、最初に一致した行を使う（`final-*`、`round-*`、`intake-*` の順）。

     | セッション内の状態 | 続き |
     | --- | --- |
     | `final-K.answers.md` が `承認`（K は最大） | SPEC を保存して片付ける（手順10） |
     | `final-K.answers.md` が `修正あり`（K は最大） | コメントを反映し、K を 1 増やして手順9を繰り返す |
     | `final-K.html` あり、`final-K.answers.md` なし（K は最大） | その HTML を開き直して、送信を待つ（手順9） |
     | `round-N.answers.md` あり、次の `round-(N+1).html` なし（N は最大） | 回答を読んで design tree を更新し、次のラウンドへ（手順8） |
     | `round-N.html` あり、`round-N.answers.md` なし（N は最大） | その HTML を開き直して、送信を待つ（手順6〜7） |
     | `intake.answers.md` あり、`round-0.*` なし | 回答に `## 更新` があれば手順2の作り直し（`render --intake --answers`）へ。なければ回答を読み、事前確認（手順3）から |
     | `intake.html` だけ（`intake.answers.md` なし） | 入力フォームを開き直して、送信を待つ（手順2） |
     | 上のどれにも当てはまらない | 状態をユーザーに見せて、続け方を聞く |
1. セッション作成: `python "${CLAUDE_PLUGIN_ROOT}/scripts/grill_form.py" init --data "${CLAUDE_PLUGIN_DATA}" --theme "<テーマ>"` を実行する。
   - テーマは ASCII の短い名前にする（Windows の Git Bash 経由の日本語引数は文字化けするため。例: `api-design`）。
   - 出力は 1 行で、`${CLAUDE_PLUGIN_DATA}/sessions/` 配下のセッション（以下 `<D>`）。HTML・回答・質問 JSON など、最終成果物以外はすべてここに置く。
   - SPEC の保存先（以下 `<S>`）は、手順10で決める。
   - セッションは、承認して SPEC を保存するまで残り、中断しても再開できる。放置したものは `list` が 14 日後に削除する。
2. 入力フォーム（毎回行う）: 依頼文・参考資料を集める。
   - 起動時にテーマ（スキルの引数・同じメッセージの依頼内容）が一緒に送られている場合は、その原文を `<D>/intake.json` に `{"request": "<原文>"}` として書き（Write）、`--input "<D>/intake.json"` を付けて依頼文欄に転記しておく（ユーザーは確認・修正だけする）。なければ空欄のままにする。
   - `python "${CLAUDE_PLUGIN_ROOT}/scripts/grill_form.py" render --session-dir "<D>" --intake [--input "<D>/intake.json"]` で `<D>/intake.html` を生成する（作業フォルダの一覧を調べて埋め込む。作業フォルダはカレントフォルダ）。
   - 手順6〜7と同じ方法で開いて送信を待つ（回答は `<D>/intake.answers.md` に書く）。フォームには、依頼文（テキストかファイル）、参考資料（作業フォルダのツリーで選ぶ。外のパスはパス欄）、「フォルダを読み直す」ボタンがある。
   - 回答に `## 更新` があるときは、ユーザーが「フォルダを読み直す」を押している（作業フォルダにファイルを足した）。`python "${CLAUDE_PLUGIN_ROOT}/scripts/grill_form.py" render --session-dir "<D>" --intake --answers "<D>/intake.answers.md"` で作り直し（入力内容とチェックは復元される）、開き直して、また送信を待つ。読み直しの回数に上限はないが、ユーザーがターミナルに入力したときは、その内容に従う。
   - `## 更新` がない回答を、次のように読む。
   - `## 依頼文` は、`- 種別:` が `テキスト` なら本文を、`ファイル` ならそのパス（1 つ）のファイルを読んで、以降の前提にする。
   - 依頼文と `## 参考資料` の各パスは、前後の引用符（`"`）を外してから、存在するファイルか確認する。存在しない・フォルダのパスは、ユーザーに再入力か対象ファイルの指定を求める。コピーはせず、元のパスのまま読み、参考資料のパスの一覧は手順9の概要の「入力」に使う。
   - PDF は pdf スキルで文字を読み、図形が重要なときは Read ツールでページを画像として見る。Word は docx スキル、PowerPoint・Excel は pptx・xlsx スキルで文字と図形の構造を読み、図形が重要なときは PDF に書き出して渡すようユーザーに伝える。量が多いときは読み取りをサブエージェントに任せてよい。
   - 入力が空（依頼文・参考資料のいずれもなし）のフォームは送信できない。ユーザーが入力不要と言ったときだけ、この手順を省略する。
3. 事前確認（Round 0）: 通常の質問に入る前に、`--round 0` で次の3点を1ラウンドで確認する。依頼文・入力ファイル・環境から分かる内容は推奨案として埋め、ユーザーには確認・修正だけしてもらう（毎回行う。小さい依頼でも省略しない）。質問 JSON・生成・回答の記録は手順4〜7と同じ。
   - 目的とゴール: 何のために行い、何ができたら完了か（完了の判定基準）。
   - 障壁: ゴールに至るまでの障害・懸念・つまずきそうな点を、ユーザーにヒアリングする。
   - 制約: 期限・予算・技術・既存資産・変更してはいけないもの・守るべきルールなど。
   回答は以降のラウンドの前提にし、SPEC では既存項目に吸収する（目的・ゴール→概要、障壁→リスク、制約→非目標・決定ログ）。
4. 質問 JSON を書く。置き場所は `<D>`、ファイル名は `<D>/round-N.json`（手順3の事前確認は `round-0.json`）。形式は `grill_form.py` の docstring を参照（`title`, `intro`, `questions[]` = `id`, `title`, `body`, `multi`, `options[]`（省略可）= `key`, `label`, `desc`、`recommended[]`, `reason`）。
5. 生成: `python "${CLAUDE_PLUGIN_ROOT}/scripts/grill_form.py" render --session-dir "<D>" --round <N> --input <json>` → `<D>/round-N.html`。
6. Playwright MCP で `browser_navigate` により `file://` URL を開く。
   - `file:///C:/.../round-N.html` のように、スラッシュ区切りにする。
   - ユーザーに「回答して『送信』を押してください」と伝える。
   - Playwright MCP の `browser_*` ツールが使えない場合は、README の「Playwright MCP を登録する」を案内して止まる（スキルには MCP を同梱していない）。`python "${CLAUDE_PLUGIN_ROOT}/scripts/grill_form.py" doctor` で不足を確認できる。
7. 送信を自動で待つ（ユーザーに「完了」と入力させない）。`browser_evaluate` で次の関数を実行すると、送信されるか約100秒たつまでブロックして結果を返す。
   `() => new Promise(res => { const t0 = Date.now(); const id = setInterval(() => { if (window.__submitted || Date.now() - t0 > 100000) { clearInterval(id); res({ submitted: !!window.__submitted, md: window.__answersMd }); } }, 500); })`
   - `submitted` が false なら、まだ送信されていない。同じ呼び出しを繰り返す（合計約30分、18回まで）。
   - ユーザーがターミナルに何か入力した場合は、待ちをやめてその内容に従う（「完了」なら即座に下の確認へ進む）。
   - 上限を超えたら、続行方法をユーザーに聞く。
   - `md` に `## 中止` がある場合は、ユーザーが HTML の「中止」ボタンで grilling を打ち切った。回答ファイルは書かず、SPEC も作らず、以降の手順に進まない。中止したことと、セッション `<D>` が残っていて再開できること（14 日後に自動で削除される）を 1 行で報告して終わる。
   - `submitted` が true で中止でないなら、`md` をそのまま `<D>/round-N.answers.md` に書く（Write）。
   - false（未送信・ウィンドウを閉じた等）なら、書かずに続行方法を聞く。コピーボタンで Markdown を貼ってもらう手もある。
8. 回答を読んで design tree を更新し、次のラウンド（手順4〜）へ。ラウンドごとに新しい HTML を生成する。
   - frontier が空になったら、手順9に進む前に、次の点検1をする。引っかかったものは、次のラウンドの質問に戻す。
   - 保留（「あとで決める」）が残っていないこと。決められないものは、理由を添えて非目標かリスクに書けば通る。
   - 回答に、判断がぶれる言葉（「適切に」「なるべく」など）が残っていないこと。
   - 依頼文と参考資料にある要求が、すべて質問か前提で扱われていること。
   - 完了の基準を、第三者が「できた／できていない」と判定できること。
9. 点検1が通ったら、合意内容を SPEC 案にまとめて、最終確認のフォームを開く。
   - SPEC 案は、概要・流れ・受入条件・非目標・リスク・決定ログで構成する。概要の中に「入力」として、依頼文の要約を少し厚めに書き、入力ファイルの元のパス一覧を入れる。
   - フォームを開く前に、クロスレビューをする。この会話の文脈を持たない新しいサブエージェントを 5 体、同時に起動する。互いの結果は見せない。各体に渡すのは、依頼文・参考資料のパス・SPEC 案・その体の観点だけ。依頼文と SPEC 案に秘密情報があれば、マスクしてから渡す。
   - 5 つの観点は次のとおり。
     1. 要件の網羅: 依頼文・参考資料の要求が、SPEC のどこで答えられているか。抜けがないか。
     2. 計画への落とし込み: SPEC に決まっていないことが残らず、writing-plans が計画を作れるか。計画を作るときに推測が要る箇所はないか。
     3. 受入条件と矛盾: 受入条件を第三者が「できた／できていない」と判定できるか。概要・流れ・受入条件・非目標・リスク・決定ログのあいだに矛盾がないか。
     4. シンプルさ: 同じ目的を、より少ない決定・手順・ロジックで達成できないか。依頼にない機能が入っていないか。
     5. リスクと非目標: リスクと非目標に漏れがないか。
   - 指摘のうち、自分だけで直せるものは直す。ユーザーの判断が要るものは、手順4に戻って質問にする。回答後は手順8の点検1からやり直す。観点どうしで指摘が衝突するとき（特に、シンプルさの削減提案が要件の網羅と衝突するとき）は、自分で選ばず、質問にする。
   - 直したあとの再レビューは 1 回まで。指摘があった観点のレビュアーだけに行う。手順4に戻ったときは、再レビューの回数を 0 に戻す。再レビューのあとに残る指摘は、SPEC のリスクに書く。
   - サブエージェントが使えないときは、同じ 5 つの観点で、自分で SPEC 案を順に読む。
   - クロスレビューの結果は、最終確認のフォームには出さない。
   - `{"title","intro","summary"}` の JSON（`<D>/final-K.json`）で `render --final --round <K>` を実行して `<D>/final-K.html` を開く。K は最終確認の版番号で、1 から始めて修正のたびに 1 増やす（前の版を上書きしない）。
   - 送信の待ち方と回答の記録は手順7と同じ（`<D>/final-K.answers.md` に書く）。
   - 回答が `修正あり` なら、コメントを反映し、K を 1 増やして、この手順9を繰り返す。`承認` なら、手順10へ進む。
10. `承認` なら、SPEC を保存して、セッションを片付ける。
   - まず `python "${CLAUDE_PLUGIN_ROOT}/scripts/grill_form.py" spec-path --theme "<テーマ>"` を実行し、出力を SPEC の保存先 `<S>`（`<作業フォルダ>/docs/grill-form/specs/<日付>-<テーマ>-design.md`）とする。`spec-path` は、保存先のフォルダがなければ作る。終了コードが 1 のとき（フォルダを作れない）は、SPEC を別の場所へ書かず、標準エラーの理由を報告して止まる。承認は有効なので、ユーザーが原因を直したあとに、この手順10をやり直す。
   - 作業フォルダはカレントフォルダで決まるので、`cd` せずに実行する。
   - 承認された版の `summary` を、次の形で `<S>` に書く（Write）。frontmatter と「後続の手順」は、最終確認のフォームの `summary` には含めず、ここで足す。別のセッションに SPEC を渡すときは、このファイルを使う。
     1. 先頭に、`---`・`status: 未対応`・`plan: （未作成）`・`---` の 4 行（frontmatter）を書く。
     2. 続けて `summary` をそのまま書く。
     3. 末尾に `## 後続の手順` の節を書く。内容は次の番号付きの 3 項目。`<計画のパス>` と `<SPEC のパス>` は、保存時に具体的な文字列で埋める。どちらも、作業フォルダからの相対パスで、区切りは `/`。
        1. 実装計画を作るときは、保存先を `<計画のパス>` にする（フォルダがなければ作る）。計画の先頭に `status: 未対応` と `spec: <SPEC のパス>` を書く。
        2. 計画を保存したら、この SPEC の先頭を `status: 完了` にし、`plan:` に `<計画のパス>` を書く。
        3. 計画の実装がすべて終わったら、計画の先頭を `status: 完了` にする。
     - `<SPEC のパス>` は `docs/grill-form/specs/` の下の `<S>` のファイル名。`<計画のパス>` は、`<S>` のファイル名の `-design` を `docs/grill-form/plans/` の下で取り除いた名前。例: `docs/grill-form/specs/2026-11-03-api-design-design-2.md` の計画は `docs/grill-form/plans/2026-11-03-api-design-2.md`（連番は引き継ぐ。テーマの中の `design` は取り除かない）。
   - 続けて、確認なしで `python "${CLAUDE_PLUGIN_ROOT}/scripts/grill_form.py" cleanup --data "${CLAUDE_PLUGIN_DATA}" --session-dir "<D>" --spec "<S>" --yes` を実行する。`cleanup` はセッション `<D>` を丸ごと削除する（`${CLAUDE_PLUGIN_DATA}/sessions/` 直下のフォルダ以外と、`<S>` がないときは何もしない）。
   - `<S>` のパスを報告し、残るのは SPEC の 1 ファイルだけであることを伝える。質問と回答の履歴は残らない。

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
入力フォームは frontmatter が `intake: 1` で、本文は `## 依頼文`（`- 種別:` に `テキスト` か `ファイル`、続けて本文またはパス）・`## 参考資料`（`- <パス>` を 1 行に 1 つ）の 2 節。「フォルダを読み直す」の回答は、先頭に `## 更新` が付き、選ばれていない側の依頼文は `## 保留の依頼文` に退避される（`render --answers` が復元する）。
どのフォームでも「中止」を 2 回押すと、本文が `## 中止`（`判定: 中止`）だけの回答になる。
最終確認は frontmatter が `round` ではなく `final: <K>`（版番号）で、本文は `## 承認` に `判定`（承認 / 修正あり）と `コメント`。

## 注意
- JS の `alert/confirm/prompt` は使わない（ブラウザ操作が止まる）。
- `file://` が開けない場合は、`--allow-unrestricted-file-access` 付きで Playwright MCP が設定されているかを確認する。
