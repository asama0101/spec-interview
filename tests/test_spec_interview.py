"""spec_interview.py のパス決定・init・描画を検査する。"""

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
sys.path.insert(0, str(ROOT / "plugins" / "spec-interview" / "scripts"))

import spec_interview  # noqa: E402

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
    monkeypatch.setattr(sys, "argv", ["spec_interview.py", *argv])
    return spec_interview.main()


SPECS = Path("docs") / "spec-interview" / "specs"


def test_spec_pathは作業フォルダのdocs配下にテーマ_日付_designを返す(workdir):
    assert spec_interview.spec_path("api-design", today=TODAY) == (
        workdir
        / "docs"
        / "spec-interview"
        / "specs"
        / "2026-10-24-api-design-design.md"
    )


def test_spec_pathは既存ファイルがあれば連番を進める(workdir):
    d = workdir / SPECS
    d.mkdir(parents=True)
    (d / "2026-10-24-api-design-design.md").write_text("1", encoding="utf-8")
    (d / "2026-10-24-api-design-design-2.md").write_text("2", encoding="utf-8")
    assert spec_interview.spec_path("api-design", today=TODAY) == (
        d / "2026-10-24-api-design-design-3.md"
    )
    assert (d / "2026-10-24-api-design-design.md").read_text("utf-8") == "1"


def test_spec_pathは記号だけのテーマをuntitledにする(workdir):
    assert spec_interview.spec_path("///", today=TODAY).name == (
        "2026-10-24-untitled-design.md"
    )


def test_spec_pathはファイルもフォルダも作らない(workdir):
    spec_interview.spec_path("t", today=TODAY)
    assert list(workdir.iterdir()) == []


def test_spec_pathサブコマンドは絶対パスを1行で出力する(workdir, monkeypatch, capsys):
    assert run(monkeypatch, "spec-path", "--theme", "demo") == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 1
    assert Path(lines[0]).parent == workdir / "docs" / "spec-interview" / "specs"
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
    assert d.name.startswith("spec-interview_demo_")
    assert list(d.iterdir()) == []


def test_initは同じテーマを続けて呼んでも別のフォルダを作る(
    temp_root, monkeypatch, capsys
):
    assert init_dir(monkeypatch, capsys) != init_dir(monkeypatch, capsys)


@pytest.mark.parametrize("theme", ["///", ' :*?"<>| '])
def test_initはパスに使えない文字だけのテーマをuntitledにする(
    theme, temp_root, monkeypatch, capsys
):
    name = init_dir(monkeypatch, capsys, theme).name
    assert name.startswith("spec-interview_untitled_")


def test_initは日本語のテーマをそのまま名前に使う(temp_root, monkeypatch, capsys):
    assert init_dir(monkeypatch, capsys, "設計").name.startswith("spec-interview_設計_")


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
    script = ROOT / "plugins" / "spec-interview" / "scripts" / "spec_interview.py"
    work = tmp_path / "作業 フォルダ"
    work.mkdir()
    env = {
        **os.environ,
        "PYTHONUTF8": "1",
        "TMP": str(temp_root),
        "TEMP": str(temp_root),
        "TMPDIR": str(temp_root),
    }
    q = work / "q.json"
    q.write_text(json.dumps({"questions": []}), encoding="utf-8")

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
        "render", "--session-dir", str(session), "--round", "1", "--input", str(q)
    )
    assert render.returncode == 0, render.stderr
    html = Path(render.stdout.strip()).read_text(encoding="utf-8")
    assert embedded_data(html)["questions"] == []

    spec = call("spec-path", "--theme", "demo")
    assert spec.returncode == 0, spec.stderr
    spec_file = Path(spec.stdout.strip())
    assert spec_file.parent == work.resolve() / "docs" / "spec-interview" / "specs"
    assert spec_file.parent.is_dir()


def test_テンプレートはinnerHTMLを使わない():
    text = (
        ROOT / "plugins" / "spec-interview" / "scripts" / "spec_interview_template.html"
    ).read_text(encoding="utf-8")
    lines = [ln for ln in text.splitlines() if "innerHTML" in ln]
    assert len(lines) == 1
    assert lines[0].strip().startswith("//")  # 「使わない」という注釈の 1 行だけ


def embedded_data(html: str) -> dict:
    start = html.index('<script id="data" type="application/json">') + len(
        '<script id="data" type="application/json">'
    )
    return json.loads(html[start : html.index("</script>", start)])


def test_テンプレートはゼロ幅スペースで依頼文を加工しない():
    text = (
        ROOT / "plugins" / "spec-interview" / "scripts" / "spec_interview_template.html"
    ).read_text(encoding="utf-8")
    assert "u200b" not in text.lower()
    assert "​" not in text


def test_埋め込みはscript終了タグを無害化する():
    out = spec_interview.embed({"tree": {"name": "a</script>b"}})
    assert "</script>" not in out
    assert "\\u003c/script>" in out


def test_埋め込みはscriptの途中で解釈される開始記号を無害化する():
    data = {"body": "コメント <!-- のあとの <script> x"}
    out = spec_interview.embed(data)
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
    assert embedded_data(html)["questions"] == questions


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
    monkeypatch.setattr(spec_interview.shutil, "which", lambda name: which)
    monkeypatch.setattr(
        spec_interview.subprocess, "run", lambda *a, **k: _Done(returncode, stdout)
    )


def test_doctorは_file_URLを許可する引数がなければ1で終わる(monkeypatch, capsys):
    _fake_claude(monkeypatch, stdout=b"playwright:\n  Args: @playwright/mcp@latest\n")
    assert run(monkeypatch, "doctor") == 3
    assert "[NG] Playwright MCP に --allow-unrestricted-file-access" in (
        capsys.readouterr().out
    )


def test_doctorは依存がそろっていれば0で終わる(monkeypatch, capsys):
    _fake_claude(monkeypatch)
    assert run(monkeypatch, "doctor") == 0
    assert "NG" not in capsys.readouterr().out


def test_doctorはclaudeがなければ不足を出して1で終わる(monkeypatch, capsys):
    _fake_claude(monkeypatch, which=None)
    assert run(monkeypatch, "doctor") == 3
    assert "[NG] claude" in capsys.readouterr().out


def test_doctorはPlaywright_MCPが未登録なら1で終わる(monkeypatch, capsys):
    _fake_claude(monkeypatch, returncode=1)
    assert run(monkeypatch, "doctor") == 3
    assert "[NG] Playwright MCP" in capsys.readouterr().out


def test_doctorはPythonが古ければ1で終わる(monkeypatch, capsys):
    _fake_claude(monkeypatch)
    monkeypatch.setattr(spec_interview, "MIN_PYTHON", (99, 0))
    assert run(monkeypatch, "doctor") == 3
    assert "[NG] Python" in capsys.readouterr().out


@pytest.fixture(autouse=True)
def _no_network_no_home(monkeypatch, tmp_path_factory):
    # doctor の版確認が、実際のネットワークと利用者の登録情報に触れないようにする
    monkeypatch.setattr(spec_interview, "latest_version", lambda: None)
    monkeypatch.setattr(
        spec_interview,
        "KNOWN_MARKETPLACES",
        tmp_path_factory.mktemp("home") / "known_marketplaces.json",
    )


def _register_marketplace(monkeypatch, tmp_path, data):
    f = tmp_path / "known.json"
    f.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(spec_interview, "KNOWN_MARKETPLACES", f)


GITHUB_ENTRY = {
    "spec-interview": {"source": {"source": "github", "repo": spec_interview.REPO}}
}


def test_doctorは現在の版を表示する(monkeypatch, capsys):
    _fake_claude(monkeypatch)
    run(monkeypatch, "doctor")
    assert f"現在の版は {spec_interview.__version__}" in capsys.readouterr().out


def test_doctorはGitHub未登録なら最新版の確認を省略する(monkeypatch, capsys):
    _fake_claude(monkeypatch)
    called = []
    monkeypatch.setattr(spec_interview, "latest_version", lambda: called.append(1))
    assert run(monkeypatch, "doctor") == 0
    assert called == []
    assert "最新版の確認は省略" in capsys.readouterr().out


def test_doctorは新しい版があれば知らせるが0で終わる(monkeypatch, capsys, tmp_path):
    _fake_claude(monkeypatch)
    _register_marketplace(monkeypatch, tmp_path, GITHUB_ENTRY)
    monkeypatch.setattr(spec_interview, "latest_version", lambda: "99.0.0")
    assert run(monkeypatch, "doctor") == 0
    out = capsys.readouterr().out
    assert "新しい版 99.0.0 があります" in out
    assert "NG" not in out


def test_doctorは同じ版なら最新版と知らせる(monkeypatch, capsys, tmp_path):
    _fake_claude(monkeypatch)
    _register_marketplace(monkeypatch, tmp_path, GITHUB_ENTRY)
    monkeypatch.setattr(
        spec_interview, "latest_version", lambda: spec_interview.__version__
    )
    run(monkeypatch, "doctor")
    assert "最新版です" in capsys.readouterr().out


def test_doctorは現在の版が新しくても更新を促さない(monkeypatch, capsys, tmp_path):
    _fake_claude(monkeypatch)
    _register_marketplace(monkeypatch, tmp_path, GITHUB_ENTRY)
    monkeypatch.setattr(spec_interview, "latest_version", lambda: "0.0.1")
    run(monkeypatch, "doctor")
    out = capsys.readouterr().out
    assert "があります" not in out
    assert "最新版です" in out


def test_doctorは最新版を取得できなくても0で終わる(monkeypatch, capsys, tmp_path):
    _fake_claude(monkeypatch)
    _register_marketplace(monkeypatch, tmp_path, GITHUB_ENTRY)
    assert run(monkeypatch, "doctor") == 0
    assert "最新版を確認できませんでした" in capsys.readouterr().out


@pytest.mark.parametrize(
    "data",
    [
        {"x": {"source": {"source": "github", "repo": "other/repo"}}},
        {"x": {"source": {"source": "directory", "path": "."}}},
        [1, 2],
    ],
)
def test_登録はこのリポジトリのGitHubだけを数える(monkeypatch, tmp_path, data):
    _register_marketplace(monkeypatch, tmp_path, data)
    assert spec_interview.github_marketplace_registered() is False


def test_登録ファイルが壊れていれば未登録として扱う(monkeypatch, tmp_path):
    f = tmp_path / "known.json"
    f.write_text("{壊れた", encoding="utf-8")
    monkeypatch.setattr(spec_interview, "KNOWN_MARKETPLACES", f)
    assert spec_interview.github_marketplace_registered() is False


def test_登録されていればTrue(monkeypatch, tmp_path):
    _register_marketplace(monkeypatch, tmp_path, GITHUB_ENTRY)
    assert spec_interview.github_marketplace_registered() is True


class _Resp:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self.body


# latest_version 自体を試すテストは、autouse の置き換えを外した本物を使う
_REAL_LATEST = spec_interview.latest_version


def test_latest_versionはplugin_jsonの版を返す(monkeypatch):
    monkeypatch.setattr(
        spec_interview.urllib.request,
        "urlopen",
        lambda url, timeout: _Resp(b'{"version": "3.1.4"}'),
    )
    assert _REAL_LATEST() == "3.1.4"


@pytest.mark.parametrize("body", [b"{broken", b"[1]", b'{"name": "x"}'])
def test_latest_versionは読めなければNone(monkeypatch, body):
    monkeypatch.setattr(
        spec_interview.urllib.request, "urlopen", lambda url, timeout: _Resp(body)
    )
    assert _REAL_LATEST() is None


def test_latest_versionは通信できなければNone(monkeypatch):
    def down(url, timeout):
        raise OSError("offline")

    monkeypatch.setattr(spec_interview.urllib.request, "urlopen", down)
    assert _REAL_LATEST() is None


def test_doctorは何も作らない(monkeypatch, workdir, tmp_path):
    _fake_claude(monkeypatch)
    run(monkeypatch, "doctor")
    assert list(workdir.iterdir()) == []
    assert list(tmp_path.iterdir()) == [workdir]


def test_doctorはclaudeが応答しないときタイムアウトで1を返す(monkeypatch, capsys):
    monkeypatch.setattr(spec_interview.shutil, "which", lambda name: "claude")

    def hang(*a, **k):
        raise subprocess.TimeoutExpired("claude", k["timeout"])

    monkeypatch.setattr(spec_interview.subprocess, "run", hang)
    assert run(monkeypatch, "doctor") == 3
    assert "[NG] Playwright MCP" in capsys.readouterr().out


def test_doctorはclaudeを実行できないときOSErrorで落ちず1を返す(monkeypatch, capsys):
    monkeypatch.setattr(spec_interview.shutil, "which", lambda name: "claude")

    def broken(*a, **k):
        raise PermissionError("claude")

    monkeypatch.setattr(spec_interview.subprocess, "run", broken)
    assert run(monkeypatch, "doctor") == 3
    assert "[NG] Playwright MCP" in capsys.readouterr().out


@pytest.mark.parametrize("text", ["{壊れた", "[1, 2]", ""])
def test_renderは壊れた入力JSONを短いエラーと終了コード2で返す(
    workdir, tmp_path, monkeypatch, capsys, text
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
        "--round",
        "1",
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


def js_eval(pattern: str, expr: str, prelude: str = ""):
    # テンプレートの pattern に合う部分を取り出し、expr を node で実行して JSON で返す
    src = spec_interview.TEMPLATE.read_text(encoding="utf-8")
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
