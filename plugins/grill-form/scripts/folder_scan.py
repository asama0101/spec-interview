"""入力フォーム用に、作業フォルダのフォルダとファイルを調べる。"""

from __future__ import annotations

import os
import stat
from pathlib import Path

MAX_DEPTH = 3  # 作業フォルダを 0、直下を 1 とした、含めるフォルダの深さの上限
MAX_ENTRIES = 200  # 1 フォルダで拾うフォルダとファイルの合計
MAX_TOTAL = 5000  # 全体の合計（巨大な作業フォルダで固まらないための上限）
MAX_DIRS = 20000  # 調べるフォルダ数（資料のないフォルダは MAX_TOTAL に入らない）
EXTS = frozenset({".docx", ".pdf", ".pptx", ".xlsx", ".md", ".txt"})
SKIP_DIRS = frozenset({".git", "node_modules", "__pycache__"})

_LINK_TAGS = {
    getattr(stat, "IO_REPARSE_TAG_MOUNT_POINT", -1),
    getattr(stat, "IO_REPARSE_TAG_SYMLINK", -1),
}
_HIDDEN = getattr(stat, "FILE_ATTRIBUTE_HIDDEN", 0) | getattr(
    stat, "FILE_ATTRIBUTE_SYSTEM", 0
)


def _skip(p: Path) -> bool:
    # 隠し・Office のロックファイル・リンク（ジャンクション含む）は出さない。
    # OneDrive のクラウドのファイルも再解析ポイントなので、タグでリンクだけを除く
    if p.name.startswith((".", "~$")) or p.name in SKIP_DIRS:
        return True
    try:
        st = p.lstat()
    except OSError:
        return True
    if stat.S_ISLNK(st.st_mode) or getattr(st, "st_reparse_tag", 0) in _LINK_TAGS:
        return True
    return bool(getattr(st, "st_file_attributes", 0) & _HIDDEN)


def _node(path: Path, depth: int, budget: list[int]) -> dict:
    # budget = [残りの件数, 残りのフォルダ数]
    node = {
        "name": path.name,
        "path": str(path),
        "dirs": [],
        "files": [],
        "truncated": False,
    }
    try:
        with os.scandir(path) as it:
            entries = sorted(it, key=lambda e: e.name.lower())
    except OSError:
        # 読めないフォルダは、中身が一部しか見えない印を付けて出す
        node["truncated"] = True
        return node
    kept = 0
    for e in entries:
        is_dir = e.is_dir(follow_symlinks=False)
        # 対象外の拡張子は、lstat を呼ぶ前に落とす（大きなフォルダで遅くならないように）
        if not is_dir and Path(e.name).suffix.lower() not in EXTS:
            continue
        p = Path(e.path)
        if _skip(p):
            continue
        if is_dir and depth + 1 > MAX_DEPTH:
            continue
        if kept >= MAX_ENTRIES or budget[0] <= 0:
            node["truncated"] = True
            break
        if is_dir and budget[1] <= 0:
            # フォルダだけ飛ばす。あとに続くファイルは落とさない
            node["truncated"] = True
            continue
        kept += 1
        budget[0] -= 1
        if not is_dir:
            node["files"].append(p.name)
            continue
        budget[1] -= 1
        child = _node(p, depth + 1, budget)
        if child["dirs"] or child["files"] or child["truncated"]:
            node["dirs"].append(child)
        else:
            # 選べるファイルがないフォルダは出さず、件数の上限も使わない
            kept -= 1
            budget[0] += 1
    return node


def scan(root: Path) -> dict:
    return _node(root, 0, [MAX_TOTAL, MAX_DIRS])
