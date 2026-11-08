"""grill_form.py のパス決定・init・入力フォームを検査する。"""

import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "plugins" / "grill-form" / "scripts"))

import grill_form  # noqa: E402

NODE = shutil.which("node")

TODAY = datetime.date(2026, 10, 24)


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    # 作業フォルダ（スクリプトのカレントフォルダ）
    d = tmp_path / "work dir 作業"
    d.mkdir()
    monkeypatch.chdir(d)
    return d


def run(monkeypatch, *argv):
    monkeypatch.setattr(sys, "argv", ["grill_form.py", *argv])
    return grill_form.main()


SPECS = Path("docs") / "grill-form" / "specs"


def test_spec_pathは作業フォルダのdocs配下にテーマ_日付_designを返す(workdir):
    assert grill_form.spec_path("api-design", today=TODAY) == (
        workdir / "docs" / "grill-form" / "specs" / "2026-10-24-api-design-design.md"
    )


def test_spec_pathは既存ファイルがあれば連番を進める(workdir):
    d = workdir / SPECS
    d.mkdir(parents=True)
    (d / "2026-10-24-api-design-design.md").write_text("1", encoding="utf-8")
    (d / "2026-10-24-api-design-design-2.md").write_text("2", encoding="utf-8")
    assert grill_form.spec_path("api-design", today=TODAY) == (
        d / "2026-10-24-api-design-design-3.md"
    )
    assert (d / "2026-10-24-api-design-design.md").read_text("utf-8") == "1"


def test_spec_pathは記号だけのテーマをuntitledにする(workdir):
    assert grill_form.spec_path("///", today=TODAY).name == (
        "2026-10-24-untitled-design.md"
    )


def test_spec_pathはファイルもフォルダも作らない(workdir):
    grill_form.spec_path("t", today=TODAY)
    assert list(workdir.iterdir()) == []


def test_spec_pathサブコマンドは絶対パスを1行で出力する(workdir, monkeypatch, capsys):
    assert run(monkeypatch, "spec-path", "--theme", "demo") == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 1
    assert Path(lines[0]).parent == workdir / "docs" / "grill-form" / "specs"
    assert Path(lines[0]).name.endswith("-demo-design.md")


def test_spec_pathサブコマンドは保存先のフォルダを作るがSPECは作らない(
    workdir, monkeypatch
):
    assert run(monkeypatch, "spec-path", "--theme", "demo") == 0
    assert (workdir / SPECS).is_dir()
    assert list((workdir / SPECS).iterdir()) == []


def test_spec_pathサブコマンドは保存先のフォルダがあっても2回続けて成功する(
    workdir, monkeypatch
):
    assert run(monkeypatch, "spec-path", "--theme", "demo") == 0
    assert run(monkeypatch, "spec-path", "--theme", "demo") == 0


def test_spec_pathサブコマンドはdocsがファイルなら終了コード1で止まる(
    workdir, monkeypatch, capsys
):
    (workdir / "docs").write_text("x", encoding="utf-8")
    assert run(monkeypatch, "spec-path", "--theme", "demo") == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "保存先のフォルダを作れません" in captured.err


def test_spec_pathサブコマンドは_parentを受け付けない(workdir, monkeypatch):
    with pytest.raises(SystemExit) as e:
        run(monkeypatch, "spec-path", "--theme", "t", "--parent", "x")
    assert e.value.code == 2


@pytest.fixture
def temp_root(tmp_path, monkeypatch):
    # OS の一時フォルダを、テスト用のフォルダに置き換える（mkdtemp の置き場）
    d = tmp_path / "一時 temp"
    d.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(d))
    return d


def init_dir(monkeypatch, capsys, theme="demo") -> Path:
    assert run(monkeypatch, "init", "--theme", theme) == 0
    return Path(capsys.readouterr().out.strip())


def test_initは一時フォルダにテーマ名つきの空のフォルダを作る(
    temp_root, monkeypatch, capsys
):
    d = init_dir(monkeypatch, capsys)
    assert d.is_dir()
    assert d.parent == temp_root
    assert d.name.startswith("grill-form_demo_")
    assert list(d.iterdir()) == []


def test_initは同じテーマを続けて呼んでも別のフォルダを作る(
    temp_root, monkeypatch, capsys
):
    assert init_dir(monkeypatch, capsys) != init_dir(monkeypatch, capsys)


@pytest.mark.parametrize("theme", ["///", ' :*?"<>| '])
def test_initはパスに使えない文字だけのテーマをuntitledにする(
    theme, temp_root, monkeypatch, capsys
):
    assert init_dir(monkeypatch, capsys, theme).name.startswith("grill-form_untitled_")


def test_initは日本語のテーマをそのまま名前に使う(temp_root, monkeypatch, capsys):
    assert init_dir(monkeypatch, capsys, "設計").name.startswith("grill-form_設計_")


@pytest.mark.parametrize(
    "argv",
    [
        ["init", "--theme", "demo", "--data", "x"],
        ["list", "--data", "x"],
        ["cleanup", "--data", "x", "--session-dir", "y", "--spec", "z"],
    ],
)
def test_廃止したサブコマンドと引数は受け付けない(argv, workdir, monkeypatch):
    with pytest.raises(SystemExit):
        run(monkeypatch, *argv)


def test_空白と日本語を含むパスで実コマンドのinitとrenderとspec_pathが通る(
    temp_root, tmp_path
):
    script = ROOT / "plugins" / "grill-form" / "scripts" / "grill_form.py"
    work = tmp_path / "作業 フォルダ"
    work.mkdir()
    env = {
        **os.environ,
        "PYTHONUTF8": "1",
        "TMP": str(temp_root),
        "TEMP": str(temp_root),
        "TMPDIR": str(temp_root),
    }
    intake = work / "入力 intake.json"
    intake.write_text(json.dumps({"request": "依頼 本文"}), encoding="utf-8")

    def call(*args):
        return subprocess.run(  # noqa: S603 自分のスクリプトを固定の引数で起動する
            [sys.executable, str(script), *args],
            cwd=work,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )

    init = call("init", "--theme", "demo")
    assert init.returncode == 0, init.stderr
    session = Path(init.stdout.strip())
    assert session.is_dir()
    assert session.resolve().parent == temp_root.resolve()

    render = call(
        "render", "--session-dir", str(session), "--intake", "--input", str(intake)
    )
    assert render.returncode == 0, render.stderr
    html = Path(render.stdout.strip()).read_text(encoding="utf-8")
    assert intake_data(html)["request"] == "依頼 本文"

    spec = call("spec-path", "--theme", "demo")
    assert spec.returncode == 0, spec.stderr
    spec_file = Path(spec.stdout.strip())
    assert spec_file.parent == work.resolve() / "docs" / "grill-form" / "specs"
    assert spec_file.parent.is_dir()


def render_intake(monkeypatch, tmp_path, capsys) -> str:
    run(monkeypatch, "render", "--session-dir", str(tmp_path / "s"), "--intake")
    return Path(capsys.readouterr().out.strip()).read_text(encoding="utf-8")


def test_テンプレートはinnerHTMLを使わない():
    text = (
        ROOT / "plugins" / "grill-form" / "scripts" / "grill_form_template.html"
    ).read_text(encoding="utf-8")
    lines = [ln for ln in text.splitlines() if "innerHTML" in ln]
    assert len(lines) == 1
    assert lines[0].strip().startswith("//")  # 「使わない」という注釈の 1 行だけ


def test_入力フォームは依頼文の欄だけを持つ(tmp_path, monkeypatch, capsys):
    html = render_intake(monkeypatch, tmp_path, capsys)
    assert "<textarea" in html or "createElement('textarea')" in html
    for gone in [
        "参考資料",
        "フォルダを読み直す",
        "Shift",
        "依頼文のファイル",
        "## 更新",
    ]:
        assert gone not in html


def test_render_intakeは_inputのrequestを初期値に埋め込む(
    tmp_path, monkeypatch, capsys
):
    j = tmp_path / "intake.json"
    j.write_text(json.dumps({"request": "依頼 本文"}), encoding="utf-8")
    run(
        monkeypatch,
        "render",
        "--session-dir",
        str(tmp_path / "s"),
        "--intake",
        "--input",
        str(j),
    )
    data = intake_data(Path(capsys.readouterr().out.strip()).read_text("utf-8"))
    assert data["request"] == "依頼 本文"
    assert "tree" not in data


def test_render_intakeは_answersを受け付けない(tmp_path, monkeypatch):
    with pytest.raises(SystemExit):
        run(
            monkeypatch,
            "render",
            "--session-dir",
            str(tmp_path / "s"),
            "--intake",
            "--answers",
            str(tmp_path / "x.md"),
        )


def intake_data(html: str) -> dict:
    start = html.index('<script id="data" type="application/json">') + len(
        '<script id="data" type="application/json">'
    )
    return json.loads(html[start : html.index("</script>", start)])


def test_テンプレートはゼロ幅スペースで依頼文を加工しない():
    text = (
        ROOT / "plugins" / "grill-form" / "scripts" / "grill_form_template.html"
    ).read_text(encoding="utf-8")
    assert "u200b" not in text.lower()
    assert "​" not in text


def test_入力フォームの描画はintroを表示する():
    text = (
        ROOT / "plugins" / "grill-form" / "scripts" / "grill_form_template.html"
    ).read_text(encoding="utf-8")
    body = text[text.index("function renderIntake") :]
    body = body[: body.index("if (data.mode === 'intake')")]
    assert "data.intro" in body


def test_埋め込みはscript終了タグを無害化する():
    out = grill_form.embed({"tree": {"name": "a</script>b"}})
    assert "</script>" not in out
    assert "\\u003c/script>" in out


def test_埋め込みはscriptの途中で解釈される開始記号を無害化する():
    data = {"body": "コメント <!-- のあとの <script> x"}
    out = grill_form.embed(data)
    assert "<" not in out
    assert json.loads(out) == data


def render_round(monkeypatch, tmp_path, capsys) -> str:
    q = tmp_path / "q.json"
    q.write_text(
        '{"questions":[{"id":"Q1","title":"t","options":[{"key":"A","label":"a"}]}]}',
        encoding="utf-8",
    )
    run(
        monkeypatch,
        "render",
        "--session-dir",
        str(tmp_path / "s"),
        "--round",
        "1",
        "--input",
        str(q),
    )
    return Path(capsys.readouterr().out.strip()).read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "present",
    ["いま答えている質問", "classList.toggle('active'", "advance("],
)
def test_質問画面に現在の質問の表示と自動で進む処理がある(
    present, tmp_path, monkeypatch, capsys
):
    assert present in render_round(monkeypatch, tmp_path, capsys)


@pytest.mark.parametrize(
    "gone",
    ['id="abort"', 'class="rail"', "el('div', 'rail')", "## 中止", "'回答 ' + n"],
)
def test_質問画面に中止ボタンと質問一覧の帯がない(gone, tmp_path, monkeypatch, capsys):
    assert gone not in render_round(monkeypatch, tmp_path, capsys)


def test_質問のJSONの全項目がHTMLに埋め込まれる(tmp_path, monkeypatch, capsys):
    questions = [
        {
            "id": "Q1",
            "title": "認証方式",
            "body": "背景\n\n- 箇条書き",
            "multi": True,
            "options": [
                {"key": "A", "label": "a", "desc": "d"},
                {"key": "B", "label": "b"},
            ],
            "recommended": ["A"],
            "reason": "理由",
        },
        {"id": "Q2", "title": "自由記述の質問"},
    ]
    q = tmp_path / "q.json"
    q.write_text(json.dumps({"questions": questions}), encoding="utf-8")
    run(
        monkeypatch,
        "render",
        "--session-dir",
        str(tmp_path / "s"),
        "--round",
        "1",
        "--input",
        str(q),
    )
    html = Path(capsys.readouterr().out.strip()).read_text(encoding="utf-8")
    assert intake_data(html)["questions"] == questions


def test_推奨の候補を左の線で示していない(tmp_path, monkeypatch, capsys):
    assert "inset 4px 0 0" not in render_round(monkeypatch, tmp_path, capsys)
    assert "border-left: 4px solid var(--rec)" not in render_round(
        monkeypatch, tmp_path, capsys
    )


class _Done:
    def __init__(self, returncode, stdout=b""):
        self.returncode = returncode
        self.stdout = stdout


_MCP_GET_OK = (
    b"playwright:\n  Args: @playwright/mcp@latest --allow-unrestricted-file-access\n"
)


def _fake_claude(monkeypatch, which="claude", returncode=0, stdout=_MCP_GET_OK):
    # 外部コマンド（claude）だけを置き換える
    monkeypatch.setattr(grill_form.shutil, "which", lambda name: which)
    monkeypatch.setattr(
        grill_form.subprocess, "run", lambda *a, **k: _Done(returncode, stdout)
    )


def test_doctorは_file_URLを許可する引数がなければ1で終わる(monkeypatch, capsys):
    _fake_claude(monkeypatch, stdout=b"playwright:\n  Args: @playwright/mcp@latest\n")
    assert run(monkeypatch, "doctor") == 1
    assert "NG: Playwright MCP に --allow-unrestricted-file-access" in (
        capsys.readouterr().out
    )


def test_doctorは依存がそろっていれば0で終わる(monkeypatch, capsys):
    _fake_claude(monkeypatch)
    assert run(monkeypatch, "doctor") == 0
    assert "NG" not in capsys.readouterr().out


def test_doctorはclaudeがなければ不足を出して1で終わる(monkeypatch, capsys):
    _fake_claude(monkeypatch, which=None)
    assert run(monkeypatch, "doctor") == 1
    assert "NG: claude" in capsys.readouterr().out


def test_doctorはPlaywright_MCPが未登録なら1で終わる(monkeypatch, capsys):
    _fake_claude(monkeypatch, returncode=1)
    assert run(monkeypatch, "doctor") == 1
    assert "NG: Playwright MCP" in capsys.readouterr().out


def test_doctorはPythonが古ければ1で終わる(monkeypatch, capsys):
    _fake_claude(monkeypatch)
    monkeypatch.setattr(grill_form, "MIN_PYTHON", (99, 0))
    assert run(monkeypatch, "doctor") == 1
    assert "NG: Python" in capsys.readouterr().out


def test_doctorは何も作らない(monkeypatch, workdir, tmp_path):
    _fake_claude(monkeypatch)
    run(monkeypatch, "doctor")
    assert list(workdir.iterdir()) == []
    assert list(tmp_path.iterdir()) == [workdir]


def test_doctorはclaudeが応答しないときタイムアウトで1を返す(monkeypatch, capsys):
    monkeypatch.setattr(grill_form.shutil, "which", lambda name: "claude")

    def hang(*a, **k):
        raise subprocess.TimeoutExpired("claude", k["timeout"])

    monkeypatch.setattr(grill_form.subprocess, "run", hang)
    assert run(monkeypatch, "doctor") == 1
    assert "NG: Playwright MCP" in capsys.readouterr().out


def test_doctorはclaudeを実行できないときOSErrorで落ちず1を返す(monkeypatch, capsys):
    monkeypatch.setattr(grill_form.shutil, "which", lambda name: "claude")

    def broken(*a, **k):
        raise PermissionError("claude")

    monkeypatch.setattr(grill_form.subprocess, "run", broken)
    assert run(monkeypatch, "doctor") == 1
    assert "NG: Playwright MCP" in capsys.readouterr().out


@pytest.mark.parametrize("text", ["{壊れた", "[1, 2]", ""])
@pytest.mark.parametrize("extra", [["--round", "1"], ["--intake"]])
def test_renderは壊れた入力JSONを短いエラーと終了コード2で返す(
    workdir, tmp_path, monkeypatch, capsys, text, extra
):
    src = tmp_path / "bad.json"
    src.write_text(text, encoding="utf-8")
    code = run(
        monkeypatch,
        "render",
        "--session-dir",
        str(tmp_path / "s"),
        "--input",
        str(src),
        *extra,
    )
    assert code == 2
    err = capsys.readouterr().err
    assert "JSON" in err
    assert "Traceback" not in err


def test_renderは入力JSONがなければ短いエラーと終了コード2で返す(
    workdir, tmp_path, monkeypatch, capsys
):
    code = run(
        monkeypatch,
        "render",
        "--session-dir",
        str(tmp_path / "s"),
        "--round",
        "1",
        "--input",
        str(tmp_path / "none.json"),
    )
    assert code == 2
    assert "読めません" in capsys.readouterr().err


@pytest.mark.skipif(NODE is None, reason="node がない環境では JS を実行できない")
def test_JSの依頼文の回答は本文をそのまま入れる():
    request = "## 依頼文\n---\n本文"
    got = js_eval(
        r"  function intakeMarkdown\(.*?\n  }\n",
        f"intakeMarkdown({{request: {json.dumps(request)}}})",
        "var data = {session: 's'};",
    )
    assert got == "---\nsession: s\nintake: 1\n---\n## 依頼文\n## 依頼文\n---\n本文\n"


@pytest.mark.skipif(NODE is None, reason="node がない環境では JS を実行できない")
def test_JSの空と空白だけの依頼文は送信できない():
    got = js_eval(
        r"  function intakeError\(.*?\n  }\n",
        "[intakeError({request: ''}), intakeError({request: ' \\n '}),"
        " intakeError({request: 'x'})]",
    )
    assert got == ["依頼文を入力してください。", "依頼文を入力してください。", ""]


def js_eval(pattern: str, expr: str, prelude: str = ""):
    # テンプレートの pattern に合う部分を取り出し、expr を node で実行して JSON で返す
    src = grill_form.TEMPLATE.read_text(encoding="utf-8")
    parts = re.findall(pattern, src, re.DOTALL)
    assert parts, f"テンプレートに {pattern} がない"
    script = (
        prelude
        + "\n"
        + "\n".join(parts)
        + f"\nprocess.stdout.write(JSON.stringify({expr}));\n"
    )
    r = subprocess.run(
        [NODE, "-e", script], capture_output=True, check=True, encoding="utf-8"
    )
    return json.loads(r.stdout)


@pytest.mark.skipif(NODE is None, reason="node がない環境では JS を実行できない")
def test_JSの未回答の確認は未回答の一覧が変わるたびに出す():
    got = js_eval(
        r"  var warned = ''.*?\n  }\n",
        "[shouldWarn(['Q2']), shouldWarn(['Q2']), shouldWarn(['Q1', 'Q2']),"
        " shouldWarn(['Q1', 'Q2']), shouldWarn([])]",
    )
    assert got == [True, False, True, False, False]
