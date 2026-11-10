"""プラグインの形式を検査する（plugin-rules F1 の 1〜8）。"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "plugins" / "spec-interview"
SKILL_MD = PLUGIN / "skills" / "spec-interview" / "SKILL.md"
SCRIPT = PLUGIN / "scripts" / "spec_interview.py"
EXPECTED_NAME = "spec-interview"


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
        ["git", "ls-files", "plugins/spec-interview"],  # noqa: S607
        cwd=ROOT,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    ).stdout.split()
    for rel in (
        ".claude-plugin/plugin.json",
        "skills/spec-interview/SKILL.md",
        "scripts/spec_interview.py",
        "scripts/spec_interview_template.html",
    ):
        assert f"plugins/spec-interview/{rel}" in out


def test_リポジトリにセッションの残骸が入っていない():
    out = subprocess.run(  # noqa: S603
        ["git", "ls-files", "*session.json", "sessions/*"],  # noqa: S607
        cwd=ROOT,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    ).stdout.split()
    assert out == []


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


def test_SKILLにspec_pathの手順がある(text):
    assert "spec-path" in text


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
    assert "plugins/spec-interview/scripts/" in text


@pytest.mark.parametrize("sub", ["init", "spec-path", "render"])
def test_allowed_toolsはサブコマンドごとに絞る(text, sub):
    allowed = parse_frontmatter(text)["allowed-tools"]
    assert f'spec_interview.py" {sub} *)' in allowed
    assert 'spec_interview.py" *)' not in allowed


DOCTOR_MD = PLUGIN / "skills" / "doctor" / "SKILL.md"


def test_doctorスキルは名前がディレクトリ名と一致し自動起動しない():
    fields = parse_frontmatter(DOCTOR_MD.read_text(encoding="utf-8"))
    assert fields["name"] == DOCTOR_MD.parent.name == "doctor"
    assert fields["description"]
    assert fields["disable-model-invocation"] == "true"


@pytest.mark.parametrize("py", ["python", "python3"])
def test_doctorスキルはdoctorだけを許可する(py):
    allowed = parse_frontmatter(DOCTOR_MD.read_text(encoding="utf-8"))["allowed-tools"]
    assert (
        f'Bash({py} "${{CLAUDE_PLUGIN_ROOT}}/scripts/spec_interview.py" doctor)' in allowed
    )
    assert "*" not in allowed


def test_doctorスキルは他の絶対パスを使わず変更しないと書く():
    body = DOCTOR_MD.read_text(encoding="utf-8")
    assert "CLAUDE_SKILL_DIR" not in body
    assert "何も変更しない" in body


def test_READMEにdoctorの呼び出し方がある():
    assert "spec_interview.py doctor" in (ROOT / "README.md").read_text(encoding="utf-8")


def test_SKILLが質問JSONとfinal_JSONのファイル名を決めている(text):
    assert "`<D>/round-N.json`" in text
    assert "`<D>/final-K.json`" in text


@pytest.mark.parametrize(
    "gone",
    [
        "cleanup",
        "--data",
        "session.json",
        "Round 0",
        "事前確認",
        "点検1",
        "点検 1",
        "status:",
        "## 中止",
        "## 更新",
        "再開",
    ],
)
def test_SKILLに手放した機能の記述がない(text, gone):
    assert gone not in text


def test_SKILLに保留と聞き返しが残る間はSPEC案に進まない旨がある(text):
    assert "保留・聞き返しが残る間は SPEC 案に進まない" in text


def test_SKILLの手順の参照が実在する(text):
    section = text[text.index("## 手順") : text.index("## 回答 Markdown")]
    steps = {int(n) for n in re.findall(r"^(\d+)\. ", section, re.MULTILINE)}
    assert steps == set(range(1, 10))
    refs = set()
    for first, last in re.findall(r"手順(\d+)(?:〜(\d+))?", text):
        refs.add(int(first))
        if last:
            refs.add(int(last))
    assert refs <= steps
