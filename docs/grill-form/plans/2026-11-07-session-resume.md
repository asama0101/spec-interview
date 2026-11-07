---
status: 完了
spec: docs/grill-form/specs/2026-11-07-session-resume-design.md
---

# 中断したセッションを再開できるようにする 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** セッションを `${CLAUDE_PLUGIN_DATA}/sessions/` に置き、起動時に未完了のセッションを一覧して再開できるようにする。

**Architecture:** `grill_form.py` の `init`・`cleanup` に `--data` を足し、置き場を `<data>/sessions/` にする。新しい `list` が古いセッションを削除して一覧を出す。再開の判断は SKILL.md の表に書き、スクリプトには進捗を持たせない。

**Tech Stack:** Python 3.8 以上（標準ライブラリだけ）、pytest 9.1.1、ruff 0.17.2、`claude plugin validate`。

**Spec:** `docs/grill-form/specs/2026-11-07-session-resume-design.md`

## Global Constraints

- 作業ブランチは `feat/session-resume`。バージョンは `1.0.0` のまま。
- 保持期間は 14 日（`KEEP_DAYS = 14`）。置き場は `<data>/sessions/<日時>_<テーマ>_<乱数>/`。
- `--data` を取るのは `init`・`list`・`cleanup` だけ。`render`・`spec-path`・`doctor` は変えない。
- `--data` が空文字のときは、使い方のエラー（終了コード 2）にする。
- テキストの読み書きは `encoding="utf-8"` を明示する。スクリプトは標準ライブラリだけを使う。
- テストは pytest の関数形式。外部（時刻・外部コマンド）だけを置き換える。
- 完了の条件: `.venv/Scripts/python.exe -m pytest -q`、`.venv/Scripts/ruff.exe check .`、`.venv/Scripts/ruff.exe format --check .`、`claude plugin validate . --strict`、`claude plugin validate plugins/grill-form --strict` がすべて通る。

## Review Focus

1. `--data` が存在しない（初回）: `list` は何も出さず終了コード 0。→ Task 2
2. `session.json` が壊れている・テーマが文字列でない: `(不明)` で出し、落ちない。→ Task 2
3. テーマにタブ・改行が入っている: 出力が 1 セッション 1 行・4 列のまま。→ Task 2
4. `cleanup` に `<data>/sessions/` そのものや、その外のフォルダを渡す: 何も消さず終了コード 1。→ Task 1
5. 空白・日本語を含む `--data`（Windows の別プロセス起動）: `init`・`list`・`cleanup` が動く。→ Task 1

---

### Task 1: `--data` と置き場の移行（`init`・`cleanup`）

**Files:**
- Modify: `plugins/grill-form/scripts/grill_form.py`
- Test: `tests/test_grill_form.py`

**Interfaces:**
- Produces（Task 2 が使う）:
  - `KEEP_DAYS = 14`（現状の `3` を置き換える）
  - `def data_dir(value: str) -> Path`: argparse の `type=`。空文字は `argparse.ArgumentTypeError`。`Path(value).resolve()` を返す。
  - `def sessions_root(data: Path) -> Path`: `data / "sessions"`。
  - `session.json`: `{"theme": <str>, "created": <ISO 8601>}`。

- [ ] **Step 1: 失敗するテストを書く**（`tests/test_grill_form.py`。既存の `temp_home` を使う `init`・`cleanup` のテストを `data_dir` フィクスチャ（`tmp_path / "データ data"`）に書き換え、次を足す）
  - `test_initは_data配下のsessionsにフォルダとsession_jsonを作る`: 出力 1 行、`Path(out).parent == data/"sessions"`、`json.loads((d/"session.json").read_text("utf-8")) ["theme"] == "demo"`、`created` が `datetime.datetime.fromisoformat` で読める。
  - `test_initは_dataなしと空文字でエラーにする`（`init`・`cleanup` の両方、`SystemExit.code == 2`）。
  - `test_cleanupは_dataのsessions直下だけを消す`: sessions 直下は消える。`data/"sessions"` 自体、`data` の外、`data/"sessions"/"x"/"y"`（孫）は消さず終了コード 1。
  - `test_cleanupは大文字小文字を区別しない`（Windows のみ。`sys.platform != "win32"` なら `skip(reason="Windows のパス規則")`）: `--data` の大文字小文字を変えても消える。
  - 既存の別プロセステスト（`os_temp`・`TEMP` を使うもの）は、`--data` に空白・日本語を含むパスを渡す形に直し、`init` → `render` → `cleanup --yes` を通す。
  - `test_doctorは何も作らない`の `temp_home` は `tmp_path` に置き換え、`temp_home` フィクスチャが未使用になったら削除する。

- [ ] **Step 2: 失敗を確認する**

Run: `.venv/Scripts/python.exe -m pytest tests/test_grill_form.py -q`
Expected: 新規・書き換えたテストが FAIL（`--data` が未定義）。

- [ ] **Step 3: 実装する**（`grill_form.py`）
  - `data_dir`・`sessions_root` を足し、`KEEP_DAYS = 14` にする。
  - `init` と `cleanup` に `--data`（`type=data_dir`、必須）を足す。
  - `cmd_init`: `sessions_root(args.data)` に `tempfile.mkdtemp(prefix=…, dir=root)`（名前の形式は現状どおり）で作り、`session.json` を書く。`prune_old` の呼び出しをやめる。
  - `cmd_cleanup`: 判定を `os.path.normcase(str(d.parent)) == os.path.normcase(str(sessions_root(args.data)))` にする。メッセージの「grill-form の一時セッションではない」は「セッションではない」に直す。
  - `temp_root`・`TEMP_ROOT_NAME` を削除する（Task 2 まで `prune_old` は残し、`root` を引数で受ける今の形のまま）。docstring の `init`・`cleanup` の記述に `--data D` を足す。

- [ ] **Step 4: 通過を確認する**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: すべて PASS（`test_skill.py` の SKILL.md を見るテストは、この Task では SKILL.md を変えないので通る）。

- [ ] **Step 5: コミット**

```bash
git add plugins/grill-form/scripts/grill_form.py tests/test_grill_form.py
git commit -m "feat: init と cleanup に --data を足し、セッションを data 配下に置く"
```

---

### Task 2: `list` サブコマンドと 14 日の自動削除

**Files:**
- Modify: `plugins/grill-form/scripts/grill_form.py`
- Test: `tests/test_grill_form.py`

**Interfaces:**
- Consumes: Task 1 の `data_dir`・`sessions_root`・`KEEP_DAYS`。
- Produces:
  - `def session_mtime(d: Path) -> float`: `d` 直下（再帰なし）のファイルで最も新しい mtime。ファイルがなければ `d.stat().st_mtime`。
  - `def prune_old(root: Path) -> None`: `session_mtime` が `KEEP_DAYS` 日より古いフォルダを `shutil.rmtree(ignore_errors=True)` で削除（引数と挙動は現状から変えず、基準だけ `session_mtime` にする）。
  - `def describe_session(d: Path) -> tuple[str, str, str, str]`: `(フォルダ名, テーマ, 更新日時, 最新のファイル名)`。テーマは `session.json` の `theme`（文字列でない・壊れている・なければ `(不明)`）。更新日時は `YYYY-MM-DD HH:MM`（ローカル時刻）。最新のファイル名はファイルがなければ `(なし)`。タブ・改行（`\t`・`\r`・`\n`）は空白 1 つに置き換える。
  - `cmd_list(args) -> int`: `prune_old` のあと、更新日時の新しい順に、各セッションを `"\t".join(describe_session(d))` で 1 行ずつ出す。`sessions_root` がなければ何も出さず 0。

- [ ] **Step 1: 失敗するテストを書く**（`tests/test_grill_form.py`。`os.utime` で mtime を作る）
  - `test_listは新しい順にタブ区切りで出す`: 2 件で順序と 4 列を確かめる。最新のファイル名は、直下で最も新しいファイル。
  - `test_listは_dataがなくても何も出さず0で終わる`
  - `test_listは14日より古いセッションを削除し13日前は残す`: 15 日前（フォルダ内のファイルも 15 日前）は消え、13 日前は残る。フォルダ自体の mtime が古くても、中のファイルが新しければ残る。
  - `test_listはsession_jsonが壊れていてもテーマを不明にする`（なし・不正な JSON・`{"theme": 1}` の 3 通り）。
  - `test_listはテーマのタブと改行を空白にして1行4列を保つ`
  - `test_listはファイルがないセッションの最新ファイル名をなしにする`（`session.json` も消したフォルダ）。
  - `test_listは_dataなしと空文字でエラーにする`

- [ ] **Step 2: 失敗を確認する**

Run: `.venv/Scripts/python.exe -m pytest tests/test_grill_form.py -q -k list`
Expected: FAIL（`list` が未定義）。

- [ ] **Step 3: 実装する**（`grill_form.py`）
  - 上の Interfaces の関数を実装し、`list` サブコマンド（`--data` 必須）を足す。`prune_old` の基準を `session_mtime` に変える。
  - docstring の「サブコマンド」に `list --data D` を足す。

- [ ] **Step 4: 通過を確認する**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: すべて PASS。

- [ ] **Step 5: コミット**

```bash
git add plugins/grill-form/scripts/grill_form.py tests/test_grill_form.py
git commit -m "feat: list サブコマンドを足し、14 日より古いセッションを削除する"
```

---

### Task 3: SKILL.md・README・開発者向け文書・形式の検査

**Files:**
- Modify: `plugins/grill-form/skills/grill-form/SKILL.md`
- Modify: `README.md`
- Modify: `docs/development.md`
- Test: `tests/test_skill.py`

**Interfaces:**
- Consumes: Task 1・2 のコマンド（`init --data`・`list --data`・`cleanup --data`）。

- [ ] **Step 1: 失敗するテストを書く**（`tests/test_skill.py`）
  - 既存の `test_allowed_toolsはサブコマンドごとに絞る` の対象に `list` を足す。
  - `test_SKILLに起動時のlistと再開の手順がある`: `text` に `grill_form.py" list --data "${CLAUDE_PLUGIN_DATA}"`、`未完了`、`再開` がある。
  - `test_SKILLの再開の表に全状態がある`: spec の「SKILL.md の変更」の表の左列の語（`intake.html`、`round-N.html`、`round-N.answers.md`、`final-K.html`、`final-K.answers.md`、`承認`、`修正あり`、`どれにも当てはまらない`）がすべて `text` にある。
  - `test_SKILLのinitとcleanupにdataを渡している`: `init`・`cleanup` を呼ぶ行（`grill_form.py" init`・`grill_form.py" cleanup`）が `--data "${CLAUDE_PLUGIN_DATA}"` を含む。
  - `test_セッションの記述に3日と一時セッションが残っていない`: SKILL.md・README.md・`docs/development.md` に `3 日`・`一時セッション` がない。
  - `test_READMEに再開と14日の説明がある`: README に `14 日`、`再開` がある。

- [ ] **Step 2: 失敗を確認する**

Run: `.venv/Scripts/python.exe -m pytest tests/test_skill.py -q`
Expected: 新規のテストが FAIL。

- [ ] **Step 3: 文書を直す**
  - SKILL.md: frontmatter の `allowed-tools` に `list *` を足す（`python`・`python3`）。手順の冒頭に「未完了セッションの確認」を足す（spec の「流れ」2〜6）。再開の表を spec の「SKILL.md の変更」のとおり書く。`init`・`cleanup` の呼び出しに `--data "${CLAUDE_PLUGIN_DATA}"` を付ける。「一時セッション」を「セッション」に、「3 日」を「14 日」に直し、中止時の報告を spec のとおり直す。
  - README: 「残るもの」と手順の説明を spec の「README・docs の変更」のとおり直す。アンインストールで `${CLAUDE_PLUGIN_DATA}` が消えるかは、`claude plugin uninstall --help` と公式ドキュメントで確かめ、確かめた事実を書く（確かめられなければ「消える可能性がある」と書く）。使い方に再開の流れを足す。秘密情報が 14 日残る注意を書く。
  - `docs/development.md`: サブコマンド表（`list` を追加、`--data`）と保存先の表を直す。

- [ ] **Step 4: 全体を確認する**

Run: `.venv/Scripts/python.exe -m pytest -q`; `.venv/Scripts/ruff.exe check .`; `.venv/Scripts/ruff.exe format --check .`; `claude plugin validate . --strict`; `claude plugin validate plugins/grill-form --strict`; `git diff --check`
Expected: すべて成功（pytest は PASS とスキップ 1 件）。

- [ ] **Step 5: コミット**

```bash
git add plugins/grill-form/skills/grill-form/SKILL.md README.md docs/development.md tests/test_skill.py
git commit -m "feat: 起動時に未完了セッションを選んで再開できるようにする"
```

---

## 完了後

- [ ] 受入条件 1〜9（spec）を、テストと実機の `init` → `list` → `cleanup` で 1 つずつ確かめる。
- [ ] この計画の先頭を `status: 完了` にし、spec の先頭を `status: 完了`、`plan:` を計画のパスにする（spec の「後続の手順」2・3）。
