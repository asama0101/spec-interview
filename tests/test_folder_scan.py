"""folder_scan.py: 作業フォルダの走査（深さ・件数・除外・拡張子）を検査する。"""

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "plugins" / "grill-form" / "scripts"))

import folder_scan  # noqa: E402


@pytest.fixture
def root(tmp_path) -> Path:
    # 空白と日本語を含むフォルダで走査する
    d = tmp_path / "work dir 作業"
    d.mkdir()
    return d


def touch(base: Path, *names: str) -> None:
    for n in names:
        (base / n).write_text("x", encoding="utf-8")


def test_scanは対象の拡張子のファイルだけを返す(root):
    touch(root, "a.pdf", "b.md", "c.zip", "d.PPTX")
    tree = folder_scan.scan(root)
    assert tree["files"] == ["a.pdf", "b.md", "d.PPTX"]
    assert tree["name"] == "work dir 作業"
    assert tree["path"] == str(root)
    assert tree["truncated"] is False


def test_scanは除外の名前を出さない(root):
    for d in (".git", "node_modules", "__pycache__", "docs"):
        (root / d).mkdir()
    touch(root / "docs", "in-docs.md")
    touch(root, ".hidden.md", "~$lock.docx", "ok.md")
    tree = folder_scan.scan(root)
    assert [c["name"] for c in tree["dirs"]] == ["docs"]
    assert tree["files"] == ["ok.md"]


def test_scanは深さ3までで切る(root):
    deep = root / "a" / "b" / "c" / "d"
    deep.mkdir(parents=True)
    touch(root / "a" / "b" / "c", "in-c.md")
    touch(deep, "in-d.md")
    a = folder_scan.scan(root)["dirs"][0]
    c = a["dirs"][0]["dirs"][0]
    assert c["name"] == "c"
    assert c["files"] == ["in-c.md"]
    assert c["dirs"] == []


def test_scanは200件を超えたらtruncatedを立てる(root):
    touch(root, *[f"f{i:03}.md" for i in range(201)])
    tree = folder_scan.scan(root)
    assert len(tree["files"]) + len(tree["dirs"]) == 200
    assert tree["truncated"] is True


def test_scanは200件ちょうどならtruncatedを立てない(root):
    touch(root, *[f"f{i:03}.md" for i in range(200)])
    tree = folder_scan.scan(root)
    assert len(tree["files"]) == 200
    assert tree["truncated"] is False


def test_scanは読めないフォルダを中身なしで出す(root, monkeypatch):
    (root / "locked").mkdir()
    real = os.scandir

    def deny(path):
        if Path(path).name == "locked":
            raise PermissionError("denied")
        return real(path)

    monkeypatch.setattr(os, "scandir", deny)
    tree = folder_scan.scan(root)
    locked = tree["dirs"][0]
    assert locked["name"] == "locked"
    assert locked["dirs"] == []
    assert locked["files"] == []
    assert locked["truncated"] is True


def test_scanはシンボリックリンクを辿らない(root, tmp_path):
    target = tmp_path / "outside"
    target.mkdir()
    touch(target, "secret.md")
    try:
        (root / "link").symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("権限なし: Windows の開発者モード未設定")
    assert folder_scan.scan(root)["dirs"] == []


def test_scanは全体の件数にも上限を持つ(root, monkeypatch):
    monkeypatch.setattr(folder_scan, "MAX_TOTAL", 30)
    for i in range(10):
        d = root / f"d{i:02}"
        d.mkdir()
        touch(d, *[f"f{j}.md" for j in range(10)])

    def count(node):
        return 1 + sum(count(c) for c in node["dirs"]) + len(node["files"])

    tree = folder_scan.scan(root)
    assert count(tree) <= 31
    assert tree["truncated"] is True


def test_scanは対象外の拡張子のファイルにlstatを呼ばない(root, monkeypatch):
    touch(root, *(f"f{i}.py" for i in range(50)), "ok.md")
    calls = []
    real = folder_scan._skip
    monkeypatch.setattr(folder_scan, "_skip", lambda p: calls.append(p) or real(p))
    assert folder_scan.scan(root)["files"] == ["ok.md"]
    assert len(calls) == 1


def test_scanは対象のファイルがないフォルダを出さず上限も使わない(root, monkeypatch):
    monkeypatch.setattr(folder_scan, "MAX_ENTRIES", 3)
    for i in range(5):
        (root / f"a{i}").mkdir()
    (root / "z").mkdir()
    touch(root / "z", "x.md")
    tree = folder_scan.scan(root)
    assert [d["name"] for d in tree["dirs"]] == ["z"]
    assert tree["truncated"] is False
