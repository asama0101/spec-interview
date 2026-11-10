# spec-interview

計画や設計を、ブラウザのフォームに答えながら詰めて、SPEC（仕様書）の 1 ファイルにまとめる Claude Code 用のプラグインです。Windows 11 専用です。

## 機能

Claude の質問に、ターミナルではなくブラウザのフォームで答えます。決めることがなくなるまで質問が続き、最後に承認すると SPEC ができます。

| できること | 内容 |
| --- | --- |
| フォームで答える | 候補を選ぶ、コメントを書く、あとで決める、聞き返す、のどれかで答えます |
| 推奨案を見る | 各質問に、Claude の推奨案と理由が付きます |
| 依頼文を渡す | 依頼文をテキストで渡します。参考にする資料は、本文にパスで書くと、Claude が元の場所のまま読みます（PDF・Word・PowerPoint・Excel・Markdown・テキスト） |
| SPEC を 1 ファイルで受け取る | 概要・流れ・受入条件・非目標・リスク・決定ログをまとめた Markdown が 1 つできます。ほかのプラグインや別のセッションに、そのまま渡せます |

## 前提条件

| 必要なもの | 内容 |
| --- | --- |
| OS | Windows 11。macOS と Linux は対象外です |
| Claude Code | [Claude Code](https://docs.claude.com/en/docs/claude-code) |
| Python | 3.8 以上。標準ライブラリだけで動くので、追加のライブラリは要りません |
| Node.js | Playwright MCP を `npx` で起動するために使います。`/spec-interview:doctor` は確認しません |
| Playwright MCP | ローカルの HTML を開き、送信を検知するために使います。このプラグインには同梱していないので、導入方法の手順 3 で登録します |
| ブラウザ | Chrome か Edge を推奨します |

## 導入方法

手順 1 から 4 を、順に行います。

### 1. マーケットプレイスを追加する

Claude Code で実行します。

```
/plugin marketplace add asama0101/spec-interview
```

GitHub を使わず、手元にコピーして入れるときは、次のようにします。

```bash
git clone https://github.com/asama0101/spec-interview.git <任意のフォルダ>/spec-interview
```

```
/plugin marketplace add <任意のフォルダ>/spec-interview
```

### 2. プラグインを入れる

```
/plugin install spec-interview@spec-interview
```

- 更新は `/plugin` の画面から行います。手元にコピーしたときは、先にそのフォルダで `git pull` します。
- 反映には Claude Code の再起動が必要です。手順 3 のあとに、まとめて 1 回行います。

### 3. Playwright MCP を登録する

Git Bash で実行します。

```bash
claude mcp add playwright --scope user -- npx @playwright/mcp@latest --allow-unrestricted-file-access --output-dir "$(python -c 'import tempfile; print(tempfile.gettempdir())')/playwright-mcp"
```

| 引数 | 役割 |
| --- | --- |
| `--allow-unrestricted-file-access` | `file://` の HTML を開くために必要です |
| `--output-dir` | Playwright MCP の記録の置き場所です。指定しないと作業フォルダに `.playwright-mcp/` ができるので、OS の一時フォルダ配下にします。上のコマンドが、一時フォルダの場所を Python で調べて埋めます |

- ブラウザを指定するときは、`--browser chrome` または `--browser msedge` を足します。
- すでに `playwright` を登録していると、上書きされません。[困ったとき](#困ったとき)の手順で登録し直してください。

登録したら、Claude Code を再起動します（手順 2 の反映も、ここで済みます）。`claude mcp list` に `playwright` が出れば成功です。

### 4. 動作環境を確認する

Claude Code の中で実行します。何も変更しません。

```
/spec-interview:doctor
```

結果は Claude が日本語で知らせます。ターミナルから直接確認するときは、手元にコピーしたリポジトリの直下で次を実行します。

```bash
python plugins/spec-interview/scripts/spec_interview.py doctor
```

確認する項目は、次の 5 つです。プラグインのバージョンは最後に出します。

| 項目 | 内容 |
| --- | --- |
| OS | Windows である |
| 実行環境 | Python 3.8 以上である |
| `claude` コマンド | PATH にある |
| Playwright MCP の登録 | `playwright` の名前で登録されていて、30 秒以内に応答する |
| `file://` の許可 | 登録に `--allow-unrestricted-file-access` が付いている |

あわせて、プラグインのバージョンを `[情報]` で表示します。GitHub（`asama0101/spec-interview`）をマーケットプレイスに登録していれば、最新版かも確認します。新しい版があっても `[NG]` にはならず、終了コードも 0 です。GitHub に接続できないときは、確認できなかったと表示するだけです。

項目ごとに `[OK]` か `[NG]` と理由を出し、対処があれば次の行に「→」で書きます。`[NG]` が 1 件でもあると、終了コード 3 で終わります。`[NG]` のあとの文言と同じ見出しを、[困ったとき](#困ったとき)で探してください。

## 使い方

### コマンド

Claude Code で使えるコマンドは、次の 2 つです。

| コマンド | 内容 |
| --- | --- |
| `/spec-interview:spec-interview [テーマ]` | フォームで質問に答えて、SPEC を作ります |
| `/spec-interview:doctor` | 動作に必要なものがそろっているか確認します。何も変更しません |

### 最初の 1 回

Claude Code で、作業フォルダを開いて、次のように頼みます。

```
/spec-interview:spec-interview API の認証方式を詰めたい
```

依頼文が足りないときは、Claude がターミナルで聞きます。そのあと、ブラウザに質問のフォームが開きます。「送信」を押すと、Claude が自動で検知して次へ進みます。「grill して」だけでは起動しません。`/spec-interview:spec-interview` を呼ぶか、「spec-interview で〜」「HTML で grilling」と書いたときだけ使われます。

### 進み方

承認するまで、次の 2 つの段階が順に進みます。

| 段階 | 内容 |
| --- | --- |
| 1. 質問ラウンド | 決めることがなくなるまで、質問のフォームを繰り返します。保留と聞き返しが残っている間は、終わりません |
| 2. 最終確認 | SPEC 案が出ます。「承認」で SPEC が保存され、Claude がそのパスを知らせます。「修正あり」を選ぶと、コメントを反映した案がまた出ます |

- 最終確認の SPEC 案は、出す前に、観点の違う 5 つのレビュアーが確かめます。
- 途中でやめるときは、ターミナルに「やめる」と入力します。SPEC は作られません。

### 依頼文と資料

- 依頼文には、何を詰めたいか、背景、分かっている制約を書きます。
- 参考にする資料があれば、パスで伝えます。Claude が、元の場所のまま読みます。コピーはしません。
- 読める資料は、PDF・Word・PowerPoint・Excel・Markdown・テキストです。PDF・Word・PowerPoint・Excel は、Claude の pdf・docx・pptx・xlsx スキルで読みます。
- PDF の図形は、ページを画像として読みます。PowerPoint と Excel は文字と図形の構造だけを読むので、図形が重要なときは PDF に書き出して渡してください。
- 存在しないパスや、フォルダのパスは読めません。そのときは、Claude が再入力を求めます。

### 質問への答え方

- 未回答の質問が残っていると、1 回目の「送信」で警告が出ます。このまま送るときは、もう一度「送信」を押します。
- 候補をクリックして選びます。候補の左の文字（`A`・`B`・`C`…）は、回答に使う記号です。
- 1 つだけ選ぶ質問は、マウスで選ぶと、次の質問へ移ります。矢印キーで動かしただけでは移りません。複数選べる質問は移りません。
- 緑の札「推奨」の候補が、Claude の推奨案です。理由は候補の下に出ます。
- 「コメント」を押すとコメント欄が開きます。候補を選んだときは、理由や条件の補足になります。候補を選ばずに書いたコメントは、それ自体が回答です。候補にない答えは、こちらに書いてください。
- 今決められないときは「あとで決める」、意味が分からないときは「聞き返す」を押します。聞き返しは次のラウンドで、Claude が説明か補足質問を返します。聞き返しが残っている間は、質問は終わりません。
- 選んだ候補を取り消して、コメントだけで答えるときは、「選択をクリア」を押します。

### 残るもの

承認すると、次の 1 ファイルだけが残ります。

```
<作業フォルダ>/docs/spec-interview/specs/<日付>-<テーマ>-design.md
```

- 例: `docs/spec-interview/specs/2026-11-03-api-design-design.md`。フォルダがなければ作ります。同じテーマを同じ日に 2 回承認すると、末尾に連番（`-2`、`-3`）が付きます。既存のファイルは上書きしません。
- 実装計画は、別のスキル（superpowers の writing-plans など）で作ります。
- 概要の「入力」に、依頼文の要約と、渡した資料の元のパスが入ります。
- 依頼文の原文、質問と回答の履歴、入力ファイルは残りません。資料はコピーしないので、元のファイルを動かすと辿れなくなります。
- SPEC は、そのまま git の管理対象になります。機密を書いたときは、`.gitignore` に `docs/spec-interview/` を加えてください。

### 作業中のファイル

作業中のファイル（質問・回答・HTML）は、OS の一時フォルダの `spec-interview_<テーマ>_…` に置かれます。承認しても消さず、掃除は OS に任せます。

- 注意: 回答に秘密情報を書いたときは、OS が一時フォルダを掃除するまで残ります。気になるときは、該当のフォルダを自分で削除してください。
- アンインストールしても、SPEC と Playwright MCP の登録は残ります。Playwright MCP はほかのツールと共有するので、不要なときだけ `claude mcp remove playwright` を自分で実行します。

## 設定

設定ファイルはありません。

- 使うブラウザは、導入方法の手順 3 のコマンドで決まります。変えるときは、手順 3 を参照してください。

## 困ったとき

画面や `/spec-interview:doctor` に出る文言を、見出しにしています。

### [NG] OS

Windows 以外で実行しています。spec-interview は Windows 専用なので、Windows で使います。

### [NG] 実行環境: Python 3.8 以上が必要です。

原因: 動いた Python の版が 3.8 より古いです。

対処: Python 3.8 以上を入れて、`python --version` で版を確かめます。

### `python` コマンドが見つからない

原因: `python` が PATH にありません。この場合、`doctor` は動かないので、`[NG]` は出ません。

対処: `python3` が使えるなら、`python` を `python3` に読み替えます。Claude は、自動で読み替えます。どちらもなければ、Python 3.8 以上を入れます。

### [NG] claude コマンド: 見つかりません

原因: `claude` コマンドが PATH にありません。Playwright MCP の確認に使います。

対処: `claude --version` が通るターミナルで、もう一度実行します。

### [NG] Playwright MCP: 確認できません

原因: `playwright` の名前で登録されていないか、30 秒以内に応答がありません。

対処: `claude mcp list` で `playwright` を確認します。なければ、導入方法の手順 3 で登録し、Claude Code を再起動します。あるのに応答がないときは、`claude mcp get playwright` が接続できるかを確かめます。Playwright MCP の `browser_*` ツールがないと言われたときも、同じ対処です。

### [NG] file:// の許可: --allow-unrestricted-file-access が付いていません

原因: すでに `playwright` が登録されていて、`claude mcp add` が効いていません。`file://` のページも開けません。

対処: 次の順で登録し直します。

1. `claude mcp get playwright` で、いまの引数とスコープを確認します。
2. `claude mcp remove playwright --scope <スコープ>` で削除します。
3. 元の引数を残したまま、`--allow-unrestricted-file-access` と `--output-dir` を付けて登録し直します。
4. Claude Code を再起動します。

### スキルが起動しない

「spec-interview で〜」か「HTML で grilling」と書いて頼んでください。「grill して」だけでは、通常の `grilling` スキルが使われます。`/spec-interview:spec-interview` で直接呼ぶこともできます。入れた直後は、Claude Code を再起動し、`/plugin` で `spec-interview` が有効か確認します。

### 送信が検知されない

「送信」を押したあと、「送信しました」と出ているか確認してください。約 30 分待っても送信がないと、Claude が続行方法を聞きます。フォームの「Markdown をコピー」で、回答を貼る方法もあります。

### ファイルのパスが読めない

存在しないパスや、フォルダのパスは読めません。Claude から、再入力を求められます。

### SPEC が想定外の場所にできた

SPEC は、Claude Code を起動したフォルダの `docs/spec-interview/specs/` にできます。サブフォルダで Claude Code を起動していないか確認してください。

### 日本語のテーマ名が文字化けする

テーマ名は、ASCII の短い名前（例: `api-design`）にしてください。

## ライセンス・連絡先

[MIT](LICENSE)

`SKILL.md` の「ルール」節は、Matt Pocock 氏の [grilling スキル](https://github.com/mattpocock/skills/tree/main/skills/productivity/grilling)（MIT）を要約・翻案したものです。元のライセンス表記は [NOTICE](plugins/spec-interview/NOTICE) にあります。

不具合や要望は、[GitHub の Issues](https://github.com/asama0101/spec-interview/issues) に書いてください。
