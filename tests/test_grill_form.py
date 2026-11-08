"""grill_form.py のパス決定・cleanup・入力フォームを検査する。"""

import datetime
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "plugins" / "grill-form" / "scripts"))

import grill_form  # noqa: E402

TODAY = datetime.date(2026, 10, 24)


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    # 作業フォルダ（スクリプトのカレントフォルダ）
    d = tmp_path / "work dir 作業"
    d.mkdir()
    monkeypatch.chdir(d)
    return d


@pytest.fixture
def data_dir(tmp_path):
    # 置き場（--data）。空白と日本語を含める
    return tmp_path / "データ data"


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


def make_session(data_dir, monkeypatch, capsys):
    run(monkeypatch, "init", "--theme", "demo", "--data", str(data_dir))
    return Path(capsys.readouterr().out.strip())


def cleanup(monkeypatch, data_dir, d, spec, *extra):
    return run(
        monkeypatch,
        "cleanup",
        "--data",
        str(data_dir),
        "--session-dir",
        str(d),
        "--spec",
        str(spec),
        *extra,
    )


def test_initは_data配下のsessionsにフォルダとsession_jsonを作る(
    data_dir, monkeypatch, capsys
):
    assert run(monkeypatch, "init", "--theme", "demo", "--data", str(data_dir)) == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 1
    d = Path(lines[0])
    assert d.is_dir()
    assert d.parent == data_dir.resolve() / "sessions"
    info = json.loads((d / "session.json").read_text("utf-8"))
    assert info["theme"] == "demo"
    datetime.datetime.fromisoformat(info["created"])


@pytest.mark.parametrize("cmd", ["init", "cleanup"])
@pytest.mark.parametrize("data", [None, ""])
def test_initとcleanupは_dataなしと空文字でエラーにする(
    cmd, data, monkeypatch, tmp_path
):
    argv = (
        ["--theme", "t"]
        if cmd == "init"
        else ["--session-dir", str(tmp_path), "--spec", str(tmp_path)]
    )
    if data is not None:
        argv += ["--data", data]
    with pytest.raises(SystemExit) as e:
        run(monkeypatch, cmd, *argv)
    assert e.value.code == 2


def test_initは同じテーマを続けて呼んでも別のフォルダを作る(
    data_dir, monkeypatch, capsys
):
    first = make_session(data_dir, monkeypatch, capsys)
    second = make_session(data_dir, monkeypatch, capsys)
    assert first != second


def test_cleanupはSPECがなければ何も消さない(data_dir, workdir, monkeypatch, capsys):
    d = make_session(data_dir, monkeypatch, capsys)
    assert cleanup(monkeypatch, data_dir, d, workdir / "none.md", "--yes") == 1
    assert d.is_dir()


def test_cleanupは_yesなしでは消さない(data_dir, workdir, monkeypatch, capsys):
    d = make_session(data_dir, monkeypatch, capsys)
    spec = workdir / "SPEC-demo.md"
    spec.write_text("x", encoding="utf-8")
    assert cleanup(monkeypatch, data_dir, d, spec) == 0
    assert d.is_dir()


def test_cleanupは_yesでセッションだけを消してSPECは残す(
    data_dir, workdir, monkeypatch, capsys
):
    d = make_session(data_dir, monkeypatch, capsys)
    spec = workdir / "SPEC-demo.md"
    spec.write_text("x", encoding="utf-8")
    assert cleanup(monkeypatch, data_dir, d, spec, "--yes") == 0
    assert not d.exists()
    assert spec.read_text("utf-8") == "x"
    assert sorted(p.name for p in workdir.iterdir()) == ["SPEC-demo.md"]


def test_cleanupは_dataのsessions直下だけを消す(data_dir, workdir, monkeypatch, capsys):
    spec = workdir / "SPEC-demo.md"
    spec.write_text("x", encoding="utf-8")
    sessions = data_dir / "sessions"
    grandchild = sessions / "x" / "y"
    grandchild.mkdir(parents=True)
    outside = workdir / "other"
    outside.mkdir()
    for target in (sessions, outside, grandchild):
        assert cleanup(monkeypatch, data_dir, target, spec, "--yes") == 1
        assert target.is_dir()
    direct = sessions / "x"
    assert cleanup(monkeypatch, data_dir, direct, spec, "--yes") == 0
    assert not direct.exists()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows のパス規則")
def test_cleanupは大文字小文字を区別しない(data_dir, workdir, monkeypatch, capsys):
    d = make_session(data_dir, monkeypatch, capsys)
    spec = workdir / "SPEC-demo.md"
    spec.write_text("x", encoding="utf-8")
    other_case = Path(str(data_dir).swapcase())
    assert cleanup(monkeypatch, other_case, d, spec, "--yes") == 0
    assert not d.exists()


def render_intake(monkeypatch, tmp_path, capsys) -> str:
    run(monkeypatch, "render", "--session-dir", str(tmp_path / "s"), "--intake")
    return Path(capsys.readouterr().out.strip()).read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "gone",
    [
        "type = 'file'",
        "grill-in-",
        "downloadPicked",
        "ダウンロード",
    ],
)
def test_入力フォームにファイル選択欄の名残がない(gone, tmp_path, monkeypatch, capsys):
    assert gone not in render_intake(monkeypatch, tmp_path, capsys)


def test_入力フォームの回答は参考資料節と更新節を持つ(tmp_path, monkeypatch, capsys):
    html = render_intake(monkeypatch, tmp_path, capsys)
    assert "## 参考資料" in html
    assert "## 更新" in html
    assert "## ファイルパス" not in html
    assert "依頼文か参考資料のどちらかを入力してください。" in html


@pytest.mark.parametrize(
    "present",
    [
        "フォルダを読み直す",
        "r.name = 'kind'",
        "依頼文のファイル",
        "Shift",
    ],
)
def test_入力フォームに新しい操作の部品がある(present, tmp_path, monkeypatch, capsys):
    assert present in render_intake(monkeypatch, tmp_path, capsys)


@pytest.mark.parametrize(
    "gone",
    ["ダイアログで選ぶ", "pick-file", "ファイルパス（1 行 1 つ）"],
)
def test_入力フォームに旧いファイルパス欄の名残がない(
    gone, tmp_path, monkeypatch, capsys
):
    assert gone not in render_intake(monkeypatch, tmp_path, capsys)


def test_テンプレートはinnerHTMLを使わない():
    text = (
        ROOT / "plugins" / "grill-form" / "scripts" / "grill_form_template.html"
    ).read_text(encoding="utf-8")
    lines = [ln for ln in text.splitlines() if "innerHTML" in ln]
    assert len(lines) == 1
    assert lines[0].strip().startswith("//")  # 「使わない」という注釈の 1 行だけ


def test_入力フォームに保存先欄がない(tmp_path, monkeypatch, capsys):
    html = render_intake(monkeypatch, tmp_path, capsys)
    assert "保存先" not in html
    assert "in-pick one" not in html


@pytest.mark.parametrize(
    "gone",
    ["outSel", "outPath", "outTree", "outSum", "extraOut", "保存先", "in-pick one"],
)
def test_入力フォームのテンプレートから保存先用の変数が消えている(gone):
    text = (
        ROOT / "plugins" / "grill-form" / "scripts" / "grill_form_template.html"
    ).read_text(encoding="utf-8")
    assert gone not in text


def test_入力フォームにフォルダを選ぶボタンはない(tmp_path, monkeypatch, capsys):
    html = render_intake(monkeypatch, tmp_path, capsys)
    assert "フォルダを選ぶ" not in html
    assert "showDirectoryPicker" not in html


def test_入力フォームの保存先にダイアログで選ぶチェックはない(
    tmp_path, monkeypatch, capsys
):
    html = render_intake(monkeypatch, tmp_path, capsys)
    assert "フォルダ選択ダイアログ" not in html


def test_pick_fileサブコマンドは廃止されている(monkeypatch):
    with pytest.raises(SystemExit):
        run(monkeypatch, "pick-file")


def intake_data(html: str) -> dict:
    start = html.index('<script id="data" type="application/json">') + len(
        '<script id="data" type="application/json">'
    )
    return json.loads(html[start : html.index("</script>", start)])


def test_parse_intake_answersはテキストの依頼文を読む():
    md = (
        "---\nsession: s\nintake: 1\n---\n"
        "## 依頼文\n- 種別: テキスト\n計画を詰めたい\n2 行目\n\n"
        "## 参考資料\n- C:\\work dir\\資料\\a.pdf\n- D:\\外\\b.xlsx\n"
    )
    assert grill_form.parse_intake_answers(md) == {
        "refresh": False,
        "kind": "text",
        "request": "計画を詰めたい\n2 行目",
        "request_file": "",
        "paths": ["C:\\work dir\\資料\\a.pdf", "D:\\外\\b.xlsx"],
    }


def test_parse_intake_answersはファイルの依頼文を引用符を外して読む():
    md = (
        "---\nsession: s\nintake: 1\n---\n"
        '## 依頼文\n- 種別: ファイル\n"C:\\work\\依頼書.docx"\n\n'
        "## 参考資料\n"
    )
    got = grill_form.parse_intake_answers(md)
    assert got["kind"] == "file"
    assert got["request_file"] == "C:\\work\\依頼書.docx"
    assert got["request"] == ""
    assert got["paths"] == []


def test_parse_intake_answersは更新の印を読む():
    md = "---\nsession: s\nintake: 1\n---\n## 更新\n- 読み直し: はい\n"
    got = grill_form.parse_intake_answers(md)
    assert got["refresh"] is True


def test_parse_intake_answersは節が欠けても既定値を返す():
    assert grill_form.parse_intake_answers("---\nintake: 1\n---\n") == {
        "refresh": False,
        "kind": "text",
        "request": "",
        "request_file": "",
        "paths": [],
    }


def test_render_intakeは作業フォルダのツリーを埋め込む(
    workdir, tmp_path, monkeypatch, capsys
):
    (workdir / "資料").mkdir()
    (workdir / "資料" / "a.pdf").write_text("x", encoding="utf-8")
    data = intake_data(render_intake(monkeypatch, tmp_path, capsys))
    assert data["cwd"] == str(workdir)
    assert data["tree"]["name"] == "work dir 作業"
    assert data["tree"]["dirs"][0]["name"] == "資料"
    assert data["tree"]["dirs"][0]["files"] == ["a.pdf"]
    assert data["kind"] == "text"


def test_render_intakeは回答から入力を復元する(workdir, tmp_path, monkeypatch, capsys):
    answers = tmp_path / "intake.answers.md"
    answers.write_text(
        "---\nsession: s\nintake: 1\n---\n## 更新\n- 読み直し: はい\n\n"
        "## 依頼文\n- 種別: ファイル\nD:\\外\\依頼書.docx\n\n"
        "## 参考資料\n- D:\\外\\x.pdf\n",
        encoding="utf-8",
    )
    run(
        monkeypatch,
        "render",
        "--session-dir",
        str(tmp_path / "s"),
        "--intake",
        "--answers",
        str(answers),
    )
    html = Path(capsys.readouterr().out.strip()).read_text(encoding="utf-8")
    data = intake_data(html)
    assert data["kind"] == "file"
    assert data["request_file"] == "D:\\外\\依頼書.docx"
    assert data["paths"] == ["D:\\外\\x.pdf"]


def test_parse_intake_answersは古い形式の保存先の節を無視する():
    body = (
        "---\nintake: 1\n---\n## 依頼文\n- 種別: テキスト\n本文\n\n"
        "## 参考資料\n- C:\\w\\a.pdf\n"
    )
    got = grill_form.parse_intake_answers(body + "\n## 保存先\nC:\\w\n")
    assert got == grill_form.parse_intake_answers(body)
    assert "dest" not in got
    assert got["paths"] == ["C:\\w\\a.pdf"]


def test_parse_intake_answersは保留の依頼文から他方の入力を復元する():
    md = (
        "---\nintake: 1\n---\n## 更新\n- 読み直し: はい\n\n"
        "## 依頼文\n- 種別: ファイル\nC:\\w\\依頼書.docx\n\n"
        "## 保留の依頼文\n- 種別: テキスト\n書きかけの依頼文\n2 行目\n"
    )
    got = grill_form.parse_intake_answers(md)
    assert got["kind"] == "file"
    assert got["request_file"] == "C:\\w\\依頼書.docx"
    assert got["request"] == "書きかけの依頼文\n2 行目"


def test_parse_intake_answersは保留のファイルからも復元する():
    md = (
        "---\nintake: 1\n---\n## 依頼文\n- 種別: テキスト\n本文\n\n"
        "## 保留の依頼文\n- 種別: ファイル\nC:\\w\\x.docx\n"
    )
    got = grill_form.parse_intake_answers(md)
    assert got["kind"] == "text"
    assert got["request"] == "本文"
    assert got["request_file"] == "C:\\w\\x.docx"


def test_parse_intake_answersは依頼文の中の見出し風の行を本文として読む():
    md = "---\nintake: 1\n---\n## 依頼文\n- 種別: テキスト\n前置き\n## 背景\n詳細\n"
    got = grill_form.parse_intake_answers(md)
    assert got["request"] == "前置き\n## 背景\n詳細"


def test_parse_intake_answersは依頼文の中の既知の見出しと同じ行を本文として読む():
    md = (
        "---\nintake: 1\n---\n## 依頼文\n- 種別: テキスト\n"
        "旧仕様は次のとおり\n## 参考資料\n社内 Wiki にある\n\n"
        "## 参考資料\n- C:\\w\\a.pdf\n"
    )
    got = grill_form.parse_intake_answers(md)
    assert got["request"] == ("旧仕様は次のとおり\n## 参考資料\n社内 Wiki にある")
    assert got["paths"] == ["C:\\w\\a.pdf"]


def test_parse_intake_answersは次の行が合わない見出し風の行を節にしない():
    md = (
        "---\nintake: 1\n---\n## 依頼文\n- 種別: テキスト\n"
        "## 更新\n手順を書いた\n## 保留の依頼文\n続き\n\n"
        "## 参考資料\n"
    )
    got = grill_form.parse_intake_answers(md)
    assert got["refresh"] is False
    assert got["request"] == "## 更新\n手順を書いた\n## 保留の依頼文\n続き"
    assert got["request_file"] == ""


def test_render_intakeは空の回答で_inputの値を消さない(
    workdir, tmp_path, monkeypatch, capsys
):
    answers = tmp_path / "a.md"
    answers.write_text(
        "---\nintake: 1\n---\n## 依頼文\n- 種別: テキスト\n",
        encoding="utf-8",
    )
    j = tmp_path / "in.json"
    j.write_text(
        json.dumps({"request": "初期の依頼文"}),
        encoding="utf-8",
    )
    run(
        monkeypatch,
        "render",
        "--session-dir",
        str(tmp_path / "s"),
        "--intake",
        "--input",
        str(j),
        "--answers",
        str(answers),
    )
    html = Path(capsys.readouterr().out.strip()).read_text(encoding="utf-8")
    data = intake_data(html)
    assert data["request"] == "初期の依頼文"
    assert "dest" not in data
    assert "refresh" not in data


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
    body = body[: body.index("function lines")]
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
    ['id="side"', "いま答えている質問", "classList.toggle('active'", "advance("],
)
def test_質問画面に一覧と現在の質問の表示と自動で進む処理がある(
    present, tmp_path, monkeypatch, capsys
):
    assert present in render_round(monkeypatch, tmp_path, capsys)


def test_推奨の候補を左の線で示していない(tmp_path, monkeypatch, capsys):
    assert "inset 4px 0 0" not in render_round(monkeypatch, tmp_path, capsys)
    assert "border-left: 4px solid var(--rec)" not in render_round(
        monkeypatch, tmp_path, capsys
    )


def test_ツリーの切り捨て通知はフォルダだけに限らない文面にする():
    text = (
        ROOT / "plugins" / "grill-form" / "scripts" / "grill_form_template.html"
    ).read_text(encoding="utf-8")
    assert "一部のフォルダだけ" not in text
    assert (
        text.count("件数が多いため一部だけ表示しています。パス欄を使ってください。")
        == 2
    )


def test_空白と日本語を含むパスで実コマンドのinitとrenderとcleanupが通る(tmp_path):
    script = ROOT / "plugins" / "grill-form" / "scripts" / "grill_form.py"
    work = tmp_path / "作業 フォルダ"
    work.mkdir()
    data = tmp_path / "データ data"
    env = {**os.environ, "PYTHONUTF8": "1"}
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

    init = call("init", "--theme", "demo", "--data", str(data))
    assert init.returncode == 0, init.stderr
    session = Path(init.stdout.strip())
    assert session.is_dir()
    assert session.resolve().parent == data.resolve() / "sessions"

    render = call(
        "render", "--session-dir", str(session), "--intake", "--input", str(intake)
    )
    assert render.returncode == 0, render.stderr
    html = Path(render.stdout.strip()).read_text(encoding="utf-8")
    assert intake_data(html)["request"] == "依頼 本文"

    spec = work / "SPEC 仕様.md"
    spec.write_text("x", encoding="utf-8")
    gone = call(
        "cleanup",
        "--data",
        str(data),
        "--session-dir",
        str(session),
        "--spec",
        str(spec),
        "--yes",
    )
    assert gone.returncode == 0, gone.stderr
    assert not session.exists()


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


DAY = 86400


def make_old_session(data_dir, name, age_days, files=("session.json",), theme="t"):
    # 直下のファイルの mtime を age_days 日前にしたセッションを作る
    d = data_dir / "sessions" / name
    d.mkdir(parents=True, exist_ok=True)
    stamp = time.time() - age_days * DAY
    for f in files:
        p = d / f
        if f == "session.json":
            p.write_text(json.dumps({"theme": theme}), encoding="utf-8")
        else:
            p.write_text("x", encoding="utf-8")
        os.utime(p, (stamp, stamp))
    return d


def list_rows(monkeypatch, capsys, data_dir):
    assert run(monkeypatch, "list", "--data", str(data_dir)) == 0
    return [ln.split("\t") for ln in capsys.readouterr().out.splitlines()]


def test_listは新しい順にタブ区切りで出す(data_dir, monkeypatch, capsys):
    make_old_session(data_dir, "old", 3, ("session.json", "a.html"), theme="古い")
    make_old_session(data_dir, "new", 1, ("session.json", "b.html"), theme="新しい")
    # b.html より新しいファイルを new に足す
    newest = data_dir / "sessions" / "new" / "c.md"
    newest.write_text("x", encoding="utf-8")
    rows = list_rows(monkeypatch, capsys, data_dir)
    assert [r[0] for r in rows] == ["new", "old"]
    assert all(len(r) == 4 for r in rows)
    assert rows[0][1] == "新しい"
    assert rows[0][3] == "c.md"
    assert rows[1][3] in ("session.json", "a.html")
    datetime.datetime.strptime(rows[0][2], "%Y-%m-%d %H:%M")


def test_listは_dataがなくても何も出さず0で終わる(data_dir, monkeypatch, capsys):
    assert run(monkeypatch, "list", "--data", str(data_dir)) == 0
    assert capsys.readouterr().out == ""


def test_listは14日より古いセッションを削除し13日前は残す(
    data_dir, monkeypatch, capsys
):
    make_old_session(data_dir, "d15", 15, ("session.json", "a.html"))
    make_old_session(data_dir, "d13", 13)
    # フォルダ自体は古いが、中のファイルは新しい
    fresh = make_old_session(data_dir, "dirold", 1)
    old = time.time() - 30 * DAY
    os.utime(fresh, (old, old))
    rows = list_rows(monkeypatch, capsys, data_dir)
    assert sorted(r[0] for r in rows) == ["d13", "dirold"]
    assert not (data_dir / "sessions" / "d15").exists()


@pytest.mark.parametrize("content", [None, "{broken", '{"theme": 1}'])
def test_listはsession_jsonが壊れていてもテーマを不明にする(
    content, data_dir, monkeypatch, capsys
):
    d = make_old_session(data_dir, "s", 1)
    if content is None:
        (d / "session.json").unlink()
    else:
        (d / "session.json").write_text(content, encoding="utf-8")
    rows = list_rows(monkeypatch, capsys, data_dir)
    assert rows[0][1] == "(不明)"


def test_listはテーマのタブと改行を空白にして1行4列を保つ(
    data_dir, monkeypatch, capsys
):
    make_old_session(data_dir, "s", 1, theme="a\tb\r\nc\nd")
    rows = list_rows(monkeypatch, capsys, data_dir)
    assert len(rows) == 1
    assert len(rows[0]) == 4
    assert rows[0][1] == "a b  c d"


def test_listはファイルがないセッションの最新ファイル名をなしにする(
    data_dir, monkeypatch, capsys
):
    d = make_old_session(data_dir, "s", 1)
    (d / "session.json").unlink()
    rows = list_rows(monkeypatch, capsys, data_dir)
    assert rows[0][0] == "s"
    assert rows[0][3] == "(なし)"


@pytest.mark.parametrize("data", [None, ""])
def test_listは_dataなしと空文字でエラーにする(data, monkeypatch):
    argv = [] if data is None else ["--data", data]
    with pytest.raises(SystemExit) as e:
        run(monkeypatch, "list", *argv)
    assert e.value.code == 2


def test_listは読めないファイルを飛ばして残りで続ける(data_dir, monkeypatch, capsys):
    d = make_old_session(data_dir, "s", 1, ("session.json", "a.html"))
    real_stat = Path.stat

    def flaky(self, *args, **kwargs):
        if self.name == "a.html":
            raise PermissionError(self.name)
        return real_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", flaky)
    rows = list_rows(monkeypatch, capsys, data_dir)
    assert rows[0][0] == "s"
    assert rows[0][3] == "session.json"
    assert d.exists()


def test_listは消えたファイルを飛ばす(data_dir, monkeypatch, capsys):
    make_old_session(data_dir, "s", 1, ("session.json", "gone.html"))
    real_stat = Path.stat

    def vanishing(self, *args, **kwargs):
        if self.name == "gone.html":
            raise FileNotFoundError(self.name)
        return real_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", vanishing)
    rows = list_rows(monkeypatch, capsys, data_dir)
    assert rows[0][3] == "session.json"


def test_listは古い空のフォルダを削除し新しい空のフォルダは残す(
    data_dir, monkeypatch, capsys
):
    root = data_dir / "sessions"
    old = root / "empty-old"
    fresh = root / "empty-fresh"
    old.mkdir(parents=True)
    fresh.mkdir()
    stamp = time.time() - 15 * DAY
    os.utime(old, (stamp, stamp))
    rows = list_rows(monkeypatch, capsys, data_dir)
    assert [r[0] for r in rows] == ["empty-fresh"]
    assert not old.exists()


def test_initはsession_jsonに作業フォルダを書く(data_dir, workdir, monkeypatch, capsys):
    run(monkeypatch, "init", "--theme", "demo", "--data", str(data_dir))
    d = Path(capsys.readouterr().out.strip())
    info = json.loads((d / "session.json").read_text(encoding="utf-8"))
    assert info["cwd"] == str(workdir.resolve())


def test_listは別の作業フォルダのセッションを出さない(
    data_dir, workdir, tmp_path, monkeypatch, capsys
):
    here = make_old_session(data_dir, "here", 1)
    other = make_old_session(data_dir, "other", 1)
    nocwd = make_old_session(data_dir, "nocwd", 1)
    for d, cwd in ((here, str(workdir.resolve())), (other, str(tmp_path / "別"))):
        (d / "session.json").write_text(
            json.dumps({"theme": "t", "cwd": cwd}), encoding="utf-8"
        )
    rows = list_rows(monkeypatch, capsys, data_dir)
    # cwd を読めないセッションは、安全側で出す
    assert sorted(r[0] for r in rows) == [here.name, nocwd.name]
    assert other.is_dir()


def test_listはセッションのフォルダが読めなくても落ちない(
    data_dir, monkeypatch, capsys
):
    make_old_session(data_dir, "ok", 1)
    make_old_session(data_dir, "bad", 1)
    real_iterdir = Path.iterdir

    def broken(self):
        if self.name == "bad":
            raise PermissionError(self.name)
        return real_iterdir(self)

    monkeypatch.setattr(Path, "iterdir", broken)
    rows = list_rows(monkeypatch, capsys, data_dir)
    assert "ok" in [r[0] for r in rows]
    assert (data_dir / "sessions" / "bad").is_dir()


def test_doctorはclaudeが応答しないときタイムアウトで1を返す(monkeypatch, capsys):
    monkeypatch.setattr(grill_form.shutil, "which", lambda name: "claude")

    def hang(*a, **k):
        raise subprocess.TimeoutExpired("claude", k["timeout"])

    monkeypatch.setattr(grill_form.subprocess, "run", hang)
    assert run(monkeypatch, "doctor") == 1
    assert "NG: Playwright MCP" in capsys.readouterr().out


def test_cleanupはSPECがフォルダなら何も消さない(
    data_dir, workdir, monkeypatch, capsys
):
    run(monkeypatch, "init", "--theme", "demo", "--data", str(data_dir))
    d = Path(capsys.readouterr().out.strip())
    code = run(
        monkeypatch,
        "cleanup",
        "--data",
        str(data_dir),
        "--session-dir",
        str(d),
        "--spec",
        str(workdir),
        "--yes",
    )
    assert code == 1
    assert d.is_dir()


def test_doctorはclaudeを実行できないときOSErrorで落ちず1を返す(monkeypatch, capsys):
    monkeypatch.setattr(grill_form.shutil, "which", lambda name: "claude")

    def broken(*a, **k):
        raise PermissionError("claude")

    monkeypatch.setattr(grill_form.subprocess, "run", broken)
    assert run(monkeypatch, "doctor") == 1
    assert "NG: Playwright MCP" in capsys.readouterr().out


def test_listは古いセッションを削除できないとき標準エラーに知らせる(
    data_dir, monkeypatch, capsys
):
    make_old_session(data_dir, "stuck", 15)
    monkeypatch.setattr(grill_form.shutil, "rmtree", lambda *a, **k: None)
    assert run(monkeypatch, "list", "--data", str(data_dir)) == 0
    out, err = capsys.readouterr()
    assert "stuck" in err
    assert "削除できません" in err
    assert "stuck" in out
