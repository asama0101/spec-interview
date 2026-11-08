# grill-form 簡素化 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 本質でない機能を手放し、grilling の質問フォームと SPEC 保存だけを残して、コード・手順書・文書を小さくする。

**Architecture:** 削除が中心。各タスクは「消す機能のテストを、消えた状態を確かめるテストに書き換える → 赤を確認 → 消す → 緑を確認 → コミット」の順。質問の出し方（SKILL.md の「ルール」節、質問 JSON の形式）は触らない。

**Tech Stack:** Python 3.8+ 標準ライブラリ、単一 HTML（JS）、pytest、ruff、Playwright MCP（目視確認）。

**Spec:** `docs/grill-form/specs/2026-11-08-simplification-design.md`（実装者はこれも読む）

## Global Constraints

- Windows 11 専用。Python は標準ライブラリだけ（`requires-python >=3.8`）。
- SKILL.md の「ルール」節（`## ルール` から `## 手順` の直前まで）は 1 文字も変えない。
- 質問 JSON の形式（`id`・`title`・`body`・`multi`・`options`・`recommended`・`reason`）と、回答 Markdown の質問ごとの `選択`・`コメント`・`聞き返し`・`状態` は変えない。
- 残す機能（質問フォーム、未回答の警告、簡易 Markdown、送信の自動検知、最終確認、5 体のクロスレビュー、`doctor`、`spec-path`）の振る舞いは変えない。
- `encoding="utf-8"` を明示する。`ruff check` と `ruff format --check` が通る。
- 過去の spec と plan（`docs/grill-form/` の既存ファイル）は変更しない。
- 実行は `PYTHONUTF8=1 python -m pytest -ra`（venv は `docs/development.md` の手順。プロジェクトの外に作る）。
- 作業ブランチは `refactor/simplify`（現在の `docs/simplification-survey` の HEAD から作る）。版を上げる Task 7 だけ別ブランチ・別 PR。

## Review Focus

- 依頼文が空、または空白だけのとき、送信できない（Task 2）。
- 依頼文の本文に `## 依頼文` や `---` の行があっても、回答 Markdown に本文がそのまま入る（Task 2）。
- テーマが日本語だけ・記号だけのとき、`init` が `untitled` を含む名前で作る（Task 3）。
- 空白と日本語を含む作業フォルダで、`init` → `render` → `spec-path` が通る（Task 3）。
- 質問 JSON の全フィールド（`body`・`multi`・`options` 省略・`recommended`・`reason`）が、質問の HTML に埋め込まれる。簡素化で grilling の質問が欠けない（Task 1）。

---

### Task 1: 中止ボタンと質問一覧の帯を消す

**Files:**
- Modify: `plugins/grill-form/scripts/grill_form_template.html`（`#abort` ボタンとそのハンドラ、`buildSide` の `data.mode === 'round'` の枝、`idxLinks`・`countEl`・`syncSide` の帯の更新、`.rail` の CSS、`## 中止` を作る処理）
- Test: `tests/test_grill_form.py`

**Interfaces:**
- Produces: round モードの HTML に `id="abort"`・`class="rail"` がない。intake / final の `#side`（進み具合の欄）と、「いま答えている質問」の枠、`advance(` は残る。

- [ ] **Step 1: テストを書き換える**。`test_質問画面に一覧と現在の質問の表示と自動で進む処理がある` の `present` から `'id="side"'` を除く（`いま答えている質問`・`classList.toggle('active'`・`advance(` は残す）。新しく次を足す。
  - `test_質問画面に中止ボタンと質問一覧の帯がない`: `render_round(...)` の HTML に `id="abort"`・`class="rail"`・`## 中止`・`回答 ` + ` / `（件数表示の `'回答 ' + n + ' / '`）が含まれない。
  - `test_質問のJSONの全項目がHTMLに埋め込まれる`: `body`・`multi: true`・`recommended`・`reason` を持つ質問と、`options` を省略した質問を `render --round 1` に渡し、埋め込み JSON（`intake_data(html)`）の `questions` が入力と等しい。
- [ ] **Step 2: 赤を確認する**。Run: `PYTHONUTF8=1 python -m pytest tests/test_grill_form.py -k "中止ボタン or 質問一覧 or JSONの全項目" -ra`。Expected: 帯のテストが FAIL、全項目のテストは PASS（回帰の固定）。
- [ ] **Step 3: テンプレートから消す**。`#abort` と「中止」を 2 回押す処理、round モードの `buildSide`（`rail`・`idxLinks`・`countEl`・`syncSide` の帯の更新）、未使用になった CSS と変数を削除する。intake / final の `steps`（進み具合）は残す。`STATE_MARK` など、残す処理が使う定義は消さない。
- [ ] **Step 4: 緑を確認する**。Run: `PYTHONUTF8=1 python -m pytest tests/test_grill_form.py -ra`。Expected: PASS。
- [ ] **Step 5: Commit**。`git add -A && git commit -m "refactor: 中止ボタンと質問一覧の帯を消す"`

### Task 2: 入力フォームを依頼文のテキスト欄だけにする

**Files:**
- Modify: `plugins/grill-form/scripts/grill_form_template.html`（`renderIntake`・`intakeGet`・`intakeMarkdown`・`build` の intake 部分）
- Modify: `plugins/grill-form/scripts/grill_form.py`（`render` の intake 部分）
- Delete: `plugins/grill-form/scripts/folder_scan.py`、`tests/test_folder_scan.py`
- Test: `tests/test_grill_form.py`

**Interfaces:**
- Produces: `render --session-dir D --intake [--input J.json]`。`J.json` は `{"title","intro","request"}`（省略可）。`--answers` は廃止（指定すると argparse が終了コード 2）。埋め込み JSON に `tree`・`cwd`・`kind` を入れない。
- Produces（回答 Markdown）: `---\nsession: <フォルダ名>\nintake: 1\n---\n## 依頼文\n<本文>\n`。本文は加工せず、そのまま入れる。
- JS: `intakeGet(): { request: string }`、`intakeMarkdown(it): string`。空・空白だけの依頼文では `build()` が `{ error: '依頼文を入力してください。' }` を返す。

- [ ] **Step 1: テストを書き換える**。
  - 削除: `test_入力フォームにファイル選択欄の名残がない`、`test_入力フォームの回答は参考資料節と更新節を持つ`、`test_入力フォームに新しい操作の部品がある`、`test_入力フォームに旧いファイルパス欄の名残がない`、`test_入力フォームに保存先欄がない`、`test_入力フォームのテンプレートから保存先用の変数が消えている`、`test_入力フォームにフォルダを選ぶボタンはない`、`test_入力フォームの保存先にダイアログで選ぶチェックはない`、`test_pick_fileサブコマンドは廃止されている`、`test_parse_intake_answers*` の全部、`test_render_intakeは作業フォルダのツリーを埋め込む`、`test_render_intakeは回答から入力を復元する`、`test_render_intakeは空の回答で_inputの値を消さない`、`test_ツリーの切り捨て通知はフォルダだけに限らない文面にする`、`test_JSが作る入力フォームの回答をparse_intake_answersが読み戻せる`、`test_JSのdirOfはドライブ直下でも一覧のキーと同じ形を返す`。
  - 新規 `test_入力フォームは依頼文の欄だけを持つ`: HTML に `<textarea` があり、`参考資料`・`フォルダを読み直す`・`Shift`・`依頼文のファイル`・`## 更新`・`## 中止` がない。
  - 新規 `test_render_intakeは_inputのrequestを初期値に埋め込む`: `intake_data(html)["request"] == "依頼 本文"`、`"tree" not in data`。
  - 新規 `test_render_intakeは_answersを受け付けない`: `run(monkeypatch, "render", "--session-dir", ..., "--intake", "--answers", "x.md")` が `SystemExit`。
  - 新規（node があるときだけ。既存の `NODE` を使う skipif の形に合わせる）`test_JSの依頼文の回答は本文をそのまま入れる`: 本文が `"## 依頼文\n---\n本文"` のとき、`intakeMarkdown` の結果が `---\nsession: s\nintake: 1\n---\n## 依頼文\n## 依頼文\n---\n本文\n` と完全一致する。
  - 新規（node があるときだけ）`test_JSの空と空白だけの依頼文は送信できない`: `""` と `"  \n "` で `build()` が `{ error: '依頼文を入力してください。' }`。
  - `test_入力フォームの描画はintroを表示する` の `body.index("function lines")` は、`function lines` が消えるので、`renderIntake` の終わりを指す形に直す。
- [ ] **Step 2: 赤を確認する**。Run: `PYTHONUTF8=1 python -m pytest tests/test_grill_form.py -k "依頼文 or answers or 入力フォーム" -ra`。Expected: 新規テストが FAIL。
- [ ] **Step 3: テンプレートを書き換える**。`renderIntake` を、`data.intro`・テキスト欄（初期値 `data.request`）・送信を描くだけにする。ツリー・ファイル一覧・Shift・パス欄・「フォルダを読み直す」・`kind` の切り替え・`dirOf`・`withSep`・`drawTree`・`drawFiles`・`drawChosen`・`lines`・`refresh` を削除する。`intro` の既定文は「何を詰めたいか、背景、分かっている制約を書く。資料のパスは本文に書く」と読める文面にする。
- [ ] **Step 4: `grill_form.py` から消す**。`import folder_scan`、`INTAKE_SECTIONS`、`parse_intake_answers`、`--answers` 引数と `answers` の読み込み、`payload["tree"]`・`payload["cwd"]`・`payload.setdefault("kind", ...)`・状態の復元を削除する。`folder_scan.py` と `tests/test_folder_scan.py` を `git rm` する。
- [ ] **Step 5: 緑を確認する**。Run: `PYTHONUTF8=1 python -m pytest -ra && python -m ruff check . && python -m ruff format --check .`。Expected: PASS（`test_配布に必要なファイルがgit管理下にある` が `folder_scan.py` を要求していれば、そのテストの対象一覧から外す）。
- [ ] **Step 6: Commit**。`git add -A && git commit -m "refactor: 入力フォームを依頼文のテキスト欄だけにする"`

### Task 3: セッションを一時フォルダにして、再開と掃除の仕組みを消す

**Files:**
- Modify: `plugins/grill-form/scripts/grill_form.py`
- Test: `tests/test_grill_form.py`

**Interfaces:**
- Produces: `init --theme T`（`--data` なし）。`tempfile.mkdtemp(prefix=f"grill-form_{normalize_theme(T)}_")` で OS の一時フォルダに作り、そのパスを 1 行で出力する。`session.json` は作らない。
- Removes: サブコマンド `list`・`cleanup`、`--data` 引数、`data_dir`・`sessions_root`・`newest_file`・`mtime_of`・`session_mtime`・`prunable`・`prune_old`・`one_line`・`read_info`・`belongs_here`・`describe_session`・`cmd_list`・`cmd_cleanup`、定数 `KEEP_DAYS`。モジュール docstring の該当部分。
- Keeps: `spec-path`・`render`・`doctor`・`normalize_theme`・`spec_path`・`embed`・`read_text`・`read_payload`。

- [ ] **Step 1: テストを書き換える**。
  - 削除: `test_initは_data配下のsessionsにフォルダとsession_jsonを作る`、`test_initとcleanupは_dataなしと空文字でエラーにする`、`test_cleanup*` の全部、`test_list*` の全部、`test_initはsession_jsonに作業フォルダを書く`、`data_dir` フィクスチャと `time` の import。
  - 新規 `test_initは一時フォルダにテーマ名つきのフォルダを作る`: 出力が 1 行で、存在するフォルダで、親が `tempfile.gettempdir()`、名前が `grill-form_demo_` で始まる。`session.json` がない。
  - 新規 `test_initは同じテーマを続けて呼んでも別のフォルダを作る`。
  - 新規 `test_initは日本語だけと記号だけのテーマをuntitledにする`: テーマ `"設計"`・`"!!"` の名前に `untitled` を含む。
  - 新規 `test_initは_dataを受け付けない`・`test_listとcleanupのサブコマンドはない`: 該当引数・サブコマンドで `SystemExit`。
  - `test_空白と日本語を含むパスで実コマンドのinitとrenderとcleanupが通る` を `...initとrenderとspec-pathが通る` に直す。`cleanup` の部分を `spec-path --theme demo` に替え、出力が作業フォルダ配下の `docs/grill-form/specs/` のパスで、フォルダができていることを確かめる。作業フォルダの名前に空白と日本語を含める。
  - 後始末として、テスト内で作った一時フォルダは `shutil.rmtree` で消す（fixture にする）。
- [ ] **Step 2: 赤を確認する**。Run: `PYTHONUTF8=1 python -m pytest tests/test_grill_form.py -k "init or list or cleanup or spec-path" -ra`。Expected: 新規テストが FAIL。
- [ ] **Step 3: 実装する**。上の Removes を削除し、`cmd_init` を上の Interfaces どおりに書き換える。`ap` の説明文用の docstring から `list`・`cleanup`・`--data` を除く。未使用になった import は `ruff check --fix` で確かめて消す。
- [ ] **Step 4: 緑を確認する**。Run: `PYTHONUTF8=1 python -m pytest tests/test_grill_form.py -ra && python -m ruff check . && python -m ruff format --check .`。Expected: PASS。
- [ ] **Step 5: Commit**。`git add -A && git commit -m "refactor: セッションを一時フォルダに置き、再開と掃除の仕組みを消す"`

### Task 4: SKILL.md を書き換える

**Files:**
- Modify: `plugins/grill-form/skills/grill-form/SKILL.md`
- Test: `tests/test_skill.py`

**Interfaces:**
- Consumes: Task 2・3 の CLI（`init --theme`、`render [--intake] [--final] --session-dir --round --input`、`spec-path --theme`、`doctor`）と、Task 2 の回答 Markdown の形。
- Produces: 手順の番号を 1 から連番にする。新しい順序は、1 セッション作成、2 入力フォーム、3 質問 JSON、4 生成、5 開く、6 送信を待つ、7 回答を読んで次のラウンドへ、8 SPEC 案・クロスレビュー・最終確認、9 SPEC の保存。

- [ ] **Step 1: テストを書き換える**。
  - 削除: `test_SKILLに起動時のlistと再開の手順がある`、`test_SKILLの再開の表に全状態がある`、`test_SKILLのinitとcleanupにdataを渡している`、`test_セッションの記述に3日と一時セッションが残っていない`、`test_READMEに再開と14日の説明がある`、`test_SKILLの再開の表は新しい段階から先に一致したものを使う`、`test_SKILLのintake_answersの行は更新があれば手順2に戻る`、`test_SKILLの再開の選択肢は新しい3件までにする`。
  - `test_allowed_toolsはサブコマンドごとに絞る` の `sub` から `list`・`cleanup` を除く（`init`・`spec-path`・`render` と `doctor` が残る）。
  - 新規 `test_SKILLに手放した機能の記述がない`: SKILL.md に `cleanup`・`--data`・`session.json`・`Round 0`・`事前確認`・`点検1`・`点検 1`・`status:`・`## 中止`・`## 更新`・`再開` が含まれない。
  - 新規 `test_SKILLに保留と聞き返しが残る間はSPEC案に進まない旨がある`: `保留・聞き返しが残る間は SPEC 案に進まない` を含む。
  - 新規 `test_SKILLの手順の参照が実在する`: 本文中の `手順(\d+)` の番号が、見出しにある手順番号の範囲に収まる。
  - 既存の `test_SKILLのルールに元のgrillingの要点がある`・`test_SKILLが質問JSONとfinal_JSONのファイル名を決めている` は変えない。
- [ ] **Step 2: 赤を確認する**。Run: `PYTHONUTF8=1 python -m pytest tests/test_skill.py -ra`。Expected: 新規テストが FAIL。
- [ ] **Step 3: SKILL.md を書き換える**。
  - frontmatter の `allowed-tools` から `list`・`cleanup` を除き、`init` を `--theme` 前提の形にする（`python` と `python3` の対は残す。権限の書式が選択肢の指定を持たないため）。
  - 手順 0 と再開の表を削除する。`CLAUDE_PLUGIN_DATA` を含む記述を消す。
  - 手順 2 を、依頼文のテキスト欄だけの説明にする。起動時のテーマを `intake.json` の `request` に入れる記述、PDF・Word・PowerPoint・Excel の読み分け、パス存在確認、「入力不要と言ったときだけ省略できる」は残す。参考資料は「依頼文の本文に書かれたパス」を読む形にする。`## 更新` の作り直しループを消す。
  - Round 0（旧手順 3）と点検 1（旧手順 8 の点検 1）を削除する。旧手順 8 の末尾に「保留・聞き返しが残る間は SPEC 案に進まない」を 1 行書く。旧手順 9 の「点検 1 からやり直す」を「手順 7 に戻る」に、「点検 1 が通ったら」を「frontier が空になったら」に置き換える。
  - 旧手順 7 の `## 中止` の枝を削除する。「ユーザーがターミナルに入力した場合は待ちをやめて従う」は残す。
  - 旧手順 10 から、frontmatter（`status`・`plan`）、「後続の手順」、`cleanup` の実行を削除する。SPEC は `summary` をそのまま `spec-path` の出力先へ書く。報告では SPEC のパスを知らせる。作業ファイルは一時フォルダにあり OS が掃除することを 1 行で書く。
  - 「回答 Markdown の書式」節を、質問ラウンドと最終確認の形と、Task 2 の入力フォームの形（`intake: 1` と `## 依頼文`）に書き直す。`## 更新`・`## 保留の依頼文`・`## 参考資料`・`## 中止` の記述を削除する。
  - 「ルール」節は変えない。
- [ ] **Step 4: 緑を確認する**。Run: `PYTHONUTF8=1 python -m pytest tests/test_skill.py -ra`。さらに `git diff main -- plugins/grill-form/skills/grill-form/SKILL.md` で、`## ルール` の節に差分がないことを目で確かめる。Expected: PASS、ルール節に差分なし。
- [ ] **Step 5: Commit**。`git add -A && git commit -m "refactor: SKILL.md から手放した機能の手順を消す"`

### Task 5: README と開発メモを直す

**Files:**
- Modify: `README.md`、`docs/development.md`
- Test: `tests/test_skill.py`（既存の README の章順・開発者向け案内の検査）

**Interfaces:**
- Consumes: Task 2〜4 で決まった CLI とフォームの形。

- [ ] **Step 1: README を直す**。機能の表から「資料を渡す（ツリー）」「中断して再開する」を除き、入力フォームを依頼文のテキスト欄の説明にする。「進み方」の段階を 3 つ（入力フォーム、質問ラウンド、最終確認）にする。「中断したセッションを再開する」「入力フォーム」の表、「質問への答え方」の質問一覧の印の表、「残るもの」の `status`・`plan`・「後続の手順」、「作業中のファイルと削除」（14 日・`sessions/`）、困りごとのうち「足したファイルが一覧に出ない」「ファイルのパスが読めない（ツリー前提の部分）」「セッションの削除に失敗した」を削除または書き直す。中止は「2 回押す」ではなく、待機中にターミナルへ入力して止める説明にする。作業ファイルは一時フォルダにあり、秘密情報を書いたときは OS の掃除まで残ることを 1 行で警告する。コマンド名とフラグは `grep` でコードと照合する。
- [ ] **Step 2: `docs/development.md` を直す**。ファイル構成の表から `folder_scan.py` を除く。サブコマンドの表から `list`・`cleanup` を除き、`init` を `--theme` だけにする。「保存先」の表を、一時フォルダの 1 行にする。「フォーム目視」の注記から入力フォームのツリーの記述を除く。
- [ ] **Step 3: 検査する**。Run: `PYTHONUTF8=1 python -m pytest tests/test_skill.py -ra`。Expected: PASS（README の章順、開発者向け案内がないこと、`scripts` の置き場の記述）。
- [ ] **Step 4: Commit**。`git add -A && git commit -m "docs: README と開発メモから手放した機能を消す"`

### Task 6: 受入条件を確かめる

**Files:** なし（確認だけ。直しが出たら該当タスクの流儀で直してコミットする）

- [ ] **Step 1: 自動検査**。Run: `PYTHONUTF8=1 python -m pytest -ra && python -m ruff check . && python -m ruff format --check .`。Expected: すべて PASS。
- [ ] **Step 2: 機能名の残骸を探す**。Run: `grep -rnE "folder_scan|cleanup|prune_old|belongs_here|session\.json|Round 0|点検 ?1|status:|plan:|中止ボタン|## 中止|## 更新|parse_intake_answers" plugins README.md docs/development.md tests`。Expected: 出力なし。一般語の「中止」「list」は対象外。
- [ ] **Step 3: ルール節の不変**。Run: `git diff main -- plugins/grill-form/skills/grill-form/SKILL.md`。`## ルール` の節に差分がないことを確かめる。
- [ ] **Step 4: 行数**。Run: `wc -l plugins/grill-form/scripts/*.py plugins/grill-form/scripts/*.html plugins/grill-form/skills/*/SKILL.md`。合計が、変更前の約 1,630 行より減っていることを報告する。
- [ ] **Step 5: 通しの目視**。Playwright MCP で、新しい一時フォルダに `init` → `render --intake` → 依頼文を入力して送信 → `render --round 1`（`recommended` つき・`body` つきの質問）→ 未回答のまま送信して警告が出ることを確認 → 回答して送信 → `render --final --round 1` → 承認 → `spec-path` の出力先へ SPEC を保存、まで実際に操作する。`window.__submitted` と `window.__answersMd` が得られることも確かめ、結果（確認した画面と出力）を報告する。MCP が使えないときは、その旨と「未検証」を報告に書く。
- [ ] **Step 6: Commit なし**。直しが出なければ何もコミットしない。

### Task 7: 版を 2.0.0 に上げる（別ブランチ・別 PR）

**Files:**
- Modify: `plugins/grill-form/scripts/grill_form.py`（`__version__`）、`plugins/grill-form/.claude-plugin/plugin.json`（`version`）

- [ ] **Step 1: ブランチ**。Task 1〜6 の PR がマージされたあとの `main` から `chore/bump-2.0.0` を切る（`~/.claude/reference/git-flow.md` の版の表記に従う）。
- [ ] **Step 2: 書き換える**。`__version__ = "2.0.0"` と `"version": "2.0.0"` にする。
- [ ] **Step 3: 検査する**。Run: `PYTHONUTF8=1 python -m pytest tests/test_skill.py -k "version" -ra`。Expected: PASS（`test_versionがメタとコードで一致する`）。
- [ ] **Step 4: Commit**。`git commit -am "chore: 版を 2.0.0 に上げる"`
