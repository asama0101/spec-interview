"""プラグインの形式を検査する（plugin-rules F1 の 1〜8）。"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "plugins" / "grill-form"
SKILL_MD = PLUGIN / "skills" / "grill-form" / "SKILL.md"
SCRIPT = PLUGIN / "scripts" / "grill_form.py"
EXPECTED_NAME = "grill-form"


@pytest.fixture(scope="module")
def text() -> str:
    return SKILL_MD.read_text(encoding="utf-8")


def parse_frontmatter(text: str) -> dict:
    m = re.match(r"---\r?\n(.*?)\r?\n---\r?\n", text, re.DOTALL)
    assert m, "SKILL.md の先頭に frontmatter がない"
    fields = {}
    for line in m.group(1).splitlines():
        key, sep, value = line.partition(":")
        if sep:
            fields[key.strip()] = value.strip()
    return fields


def test_frontmatterのnameがディレクトリ名と一致する(text):
    assert parse_frontmatter(text)["name"] == SKILL_MD.parent.name == EXPECTED_NAME


def test_ハードコードした絶対パスがない(text):
    # ドライブ文字付きのパス、または /Users/<名前>・/home/<名前>。
    # 「C:/.../」のような省略記法の例は対象外にする。
    pattern = r"(?<![A-Za-z])[A-Za-z]:[\/]+\w|/(?:Users|home)/\w"
    assert re.findall(pattern, text) == []


def test_CLAUDE_SKILL_DIR_を使っていない(text):
    assert "CLAUDE_SKILL_DIR" not in text


def test_CLAUDE_PLUGIN_ROOT_が指すファイルが実在する(text):
    refs = re.findall(r"\$\{CLAUDE_PLUGIN_ROOT\}/([^\s\"'`)]+)", text)
    assert refs, "参照が 1 件もない（検査が空振りしている）"
    missing = [r for r in refs if not (PLUGIN / r).is_file()]
    assert missing == []


def test_MCPを同梱していない():
    assert not (PLUGIN / ".mcp.json").exists()
    plugin = json.loads(
        (PLUGIN / ".claude-plugin/plugin.json").read_text(encoding="utf-8")
    )
    market = json.loads(
        (ROOT / ".claude-plugin/marketplace.json").read_text(encoding="utf-8")
    )
    assert "mcpServers" not in plugin
    assert all("mcpServers" not in p for p in market["plugins"])


def test_versionがメタとコードで一致する():
    plugin = json.loads(
        (PLUGIN / ".claude-plugin/plugin.json").read_text(encoding="utf-8")
    )
    m = re.search(r'__version__ = "([^"]+)"', SCRIPT.read_text(encoding="utf-8"))
    assert m
    assert plugin["version"] == m.group(1)


def test_配布に必要なファイルがgit管理下にある():
    out = subprocess.run(  # noqa: S603
        ["git", "ls-files", "plugins/grill-form"],  # noqa: S607
        cwd=ROOT,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    ).stdout.split()
    for rel in (
        ".claude-plugin/plugin.json",
        "skills/grill-form/SKILL.md",
        "scripts/grill_form.py",
        "scripts/grill_form_template.html",
    ):
        assert f"plugins/grill-form/{rel}" in out


@pytest.mark.skipif(shutil.which("claude") is None, reason="claude CLI がない")
def test_claude_plugin_validateが通る():
    for target in (PLUGIN, ROOT):
        r = subprocess.run(  # noqa: S603
            [shutil.which("claude"), "plugin", "validate", str(target), "--strict"],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        assert r.returncode == 0, r.stdout + r.stderr


def test_相対リンクと地の文の相対パスがない(text):
    # Markdown リンクのうち、URL・アンカー以外のもの
    links = re.findall(r"\]\((?!https?://|mailto:|#)[^)]*\)", text)
    # ./ や ../ で始まるパス
    prose = re.findall(r"(?:^|[\s`(\"'])\.{1,2}/", text, re.MULTILINE)
    assert links == []
    assert prose == []


# 廃止した仕様の語。SKILL.md・README.md・grill_form.py のどれにも残さない。
REMOVED_TERMS = [
    "grill-specs",
    "request.md",
    "inputs/",
    "GRILL_FORM_DIR",
    "soffice",
    "pdftoppm",
    "ファイル選択",
    "pick-file",
    "tkinter",
]


def test_SKILLにspec_pathの手順がある(text):
    assert "spec-path" in text


def test_SKILLが存在しないパスの再入力を求める(text):
    assert "再入力" in text


@pytest.mark.parametrize("term", REMOVED_TERMS)
def test_SKILLに廃止した語が残っていない(text, term):
    assert term not in text


@pytest.mark.parametrize("term", REMOVED_TERMS)
def test_READMEとスクリプトに廃止した語が残っていない(term):
    for path in (ROOT / "README.md", SCRIPT):
        body = path.read_text(encoding="utf-8")
        assert term not in body, path.name


def test_stageサブコマンドの記述がどこにも残っていない(text):
    for path in (ROOT / "README.md", SCRIPT):
        body = path.read_text(encoding="utf-8")
        assert re.search(r"\bstage\b", body) is None, path.name
    assert re.search(r"\bstage\b", text) is None


def test_SKILLは保存先を聞かずRound0は3点のまま(text):
    assert "`## 保存先`" not in text
    assert "次の3点を" in text
    assert "次の4点を" not in text


def test_SKILLに保存先をダイアログで選ぶ手順はない(text):
    assert "pick-dir" not in text


def test_SKILLにpick_fileの手順はない(text):
    assert "pick-file" not in text
    assert "ダイアログで選ぶ" not in text


@pytest.mark.parametrize(
    "present",
    ["## 更新", "--answers", "## 参考資料", "フォルダを読み直す"],
)
def test_SKILLに読み直しと新しい回答の節の手順がある(text, present):
    assert present in text


def test_SKILLに旧いファイルパス節の記述がない(text):
    assert "## ファイルパス" not in text


@pytest.mark.parametrize(
    "present",
    [
        "点検1",
        "保留（「あとで決める」）が残っていない",
        "判断がぶれる言葉",
        "判定できる",
        "クロスレビュー",
        "文脈を持たない新しいサブエージェント",
        "矛盾がないか",
    ],
)
def test_SKILLに質問を終える前とSPEC案を出す前の点検がある(text, present):
    assert present in text


def test_SKILLの点検1は手順9より前にありクロスレビューはフォームを開く前にある(
    text,
):
    assert text.index("点検1") < text.index("\n9. ")
    assert text.index("クロスレビュー") < text.index("`render --final")


def test_SKILLに点検2の記述が残っていない(text):
    assert "点検2" not in text


@pytest.mark.parametrize(
    "perspective",
    [
        "要件の網羅",
        "計画への落とし込み",
        "受入条件と矛盾",
        "シンプルさ",
        "リスクと非目標",
    ],
)
def test_SKILLのクロスレビューに5観点がある(text, perspective):
    assert perspective in text


def test_SKILLのクロスレビューは再レビューを1回までにする(text):
    assert "再レビューは 1 回まで" in text


@pytest.mark.parametrize(
    "present",
    [
        "docs/grill-form/specs",
        "docs/grill-form/plans",
        "status: 未対応",
        "status: 完了",
        "## 後続の手順",
        "plan:",
        "spec:",
    ],
)
def test_SKILLに保存先とstatusと後続の手順の規約がある(text, present):
    assert present in text


@pytest.mark.parametrize(
    "present",
    [
        "5 体、同時に起動する",
        "---`・`status: 未対応`・`plan: （未作成）`・`---` の 4 行",
        "`<SPEC のパス>` は、保存時に具体的な文字列で埋める",
        "の計画は `docs/grill-form/plans/2026-11-03-api-design-2.md`",
        "終了コードが 1 のとき",
    ],
)
def test_SKILLの手順の要点が省かれていない(text, present):
    assert present in text


def test_SKILLのspec_pathに_parentを付けない(text):
    assert "--parent" not in text


UPSTREAM_COMMIT = "95249b0b49782349740fd9b8c6ce32b4e59e497a"
MAX_LINE = 400


def body_lines(text: str) -> list:
    # frontmatter（先頭の --- から次の --- まで）を除いた本文の行
    return re.sub(r"\A---\r?\n.*?\r?\n---\r?\n", "", text, flags=re.DOTALL).splitlines()


def test_SKILLの本文は1行が長すぎない(text):
    too_long = [
        (i, len(line))
        for i, line in enumerate(body_lines(text), 1)
        if len(line) > MAX_LINE
    ]
    assert too_long == []


@pytest.mark.parametrize(
    "rule",
    [
        "黙って仮定したまま残さない",
        "同じラウンドで未決の質問に依存する質問は、そのラウンドに出さず、次のラウンドに回す",
        "「はい」で推奨案を受け入れられる文言",
    ],
)
def test_SKILLのルールに元のgrillingの要点がある(text, rule):
    assert rule in text


def test_出典の固定する版が元の最新の版である():
    notices = (PLUGIN / "NOTICE").read_text(encoding="utf-8")
    assert UPSTREAM_COMMIT in notices


README_SECTIONS = [
    "機能",
    "前提条件",
    "導入方法",
    "使い方",
    "設定",
    "困ったとき",
    "ライセンス・連絡先",
]


def test_READMEはリポジトリ直下に1つだけある():
    found = sorted(
        p.relative_to(ROOT).as_posix()
        for p in ROOT.rglob("README.md")
        if not any(part.startswith(".") or part == "node_modules" for part in p.parts)
    )
    assert found == ["README.md"]


def test_READMEの章は規則の順番に並ぶ():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    heads = re.findall(r"^## (.+)$", text, re.MULTILINE)
    assert heads, "章（## 見出し）が 1 つもない"
    assert [h for h in README_SECTIONS if h in heads] == heads


def test_READMEは未検証の明記を本文に書かない():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "未検証" not in text


def test_READMEに開発者向けの案内がない():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "development.md" not in text
    assert "## 開発者向け" not in text


def test_READMEにscriptsの置き場が書かれている():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "plugins/grill-form/scripts/" in text


@pytest.mark.parametrize("sub", ["init", "spec-path", "render", "cleanup", "list"])
def test_allowed_toolsはサブコマンドごとに絞る(text, sub):
    allowed = parse_frontmatter(text)["allowed-tools"]
    assert f'grill_form.py" {sub} *)' in allowed
    assert 'grill_form.py" *)' not in allowed


def test_READMEにdoctorの呼び出し方がある():
    assert "grill_form.py doctor" in (ROOT / "README.md").read_text(encoding="utf-8")


def test_SKILLに起動時のlistと再開の手順がある(text):
    assert 'grill_form.py" list --data "${CLAUDE_PLUGIN_DATA}"' in text
    assert "未完了" in text
    assert "再開" in text


@pytest.mark.parametrize(
    "state",
    [
        "intake.html",
        "round-N.html",
        "round-N.answers.md",
        "final-K.html",
        "final-K.answers.md",
        "承認",
        "修正あり",
        "どれにも当てはまらない",
    ],
)
def test_SKILLの再開の表に全状態がある(text, state):
    assert state in text


@pytest.mark.parametrize("sub", ["init", "cleanup"])
def test_SKILLのinitとcleanupにdataを渡している(text, sub):
    lines = [ln for ln in text.splitlines() if f'grill_form.py" {sub}' in ln]
    body = [ln for ln in lines if not ln.startswith("allowed-tools:")]
    assert body
    assert all('--data "${CLAUDE_PLUGIN_DATA}"' in ln for ln in body)


@pytest.mark.parametrize("name", ["SKILL", "README", "development"])
def test_セッションの記述に3日と一時セッションが残っていない(name):
    path = {
        "SKILL": SKILL_MD,
        "README": ROOT / "README.md",
        "development": ROOT / "docs" / "development.md",
    }[name]
    body = path.read_text(encoding="utf-8")
    assert "3 日" not in body
    assert "一時セッション" not in body


def test_READMEに再開と14日の説明がある():
    body = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "14 日" in body
    assert "再開" in body


def test_SKILLが質問JSONとfinal_JSONのファイル名を決めている(text):
    assert "`<D>/round-N.json`" in text
    assert "`<D>/final-K.json`" in text


def test_SKILLの再開の表は新しい段階から先に一致したものを使う(text):
    assert "新しい段階" in text
    assert "最初に一致した行" in text


def test_SKILLのintake_answersの行は更新があれば手順2に戻る(text):
    row = next(ln for ln in text.splitlines() if "`intake.answers.md` あり" in ln)
    assert "## 更新" in row


def test_SKILLの再開の選択肢は新しい3件までにする(text):
    assert "新しい 3 件" in text
    assert "その他" in text
