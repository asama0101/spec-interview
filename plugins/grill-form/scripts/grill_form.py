"""grill-form スキル用のスクリプト。

サブコマンド:
  init   --theme T --data D   セッションフォルダ（D/sessions/ 配下）を作り、
                              そのパスを1行で出力する
                              （HTML・回答・質問 JSON を置く）。
                              session.json にテーマと作成日時を書く
  list   --data D             セッション（D/sessions/ 配下）を、更新の新しい順に
                              フォルダ名・テーマ・更新日時・最新のファイル名を
                              タブ区切りで1行ずつ出力する。
                              14 日より古いセッションは先に削除する
  spec-path --theme T         SPEC の保存先
                              <作業フォルダ>/docs/grill-form/specs/<日付>-<テーマ>-design.md
                              を決め、フォルダを作って、パスを出力する
                              （ファイルは作らない）。作業フォルダは、
                              このスクリプトのカレントフォルダ。
                              同名のファイルがあれば末尾に連番を付ける
  render --session-dir D --round N [--final] --input J.json
                              質問 JSON から round-N.html を生成し、パスを出力する。
                              --final のときは N を最終確認の版番号とし、
                              final-N.html を生成する
                              （修正のたびに版を上げ、前の版を上書きしない）
  render --session-dir D --intake [--input J.json] [--answers A.md]
                              入力フォーム intake.html を生成する。作業フォルダ
                              （カレントフォルダ）の一覧を調べて埋め込む。
                              J.json は {"title","intro","request"} で省略可
                              （request は依頼文欄の初期入力）。
                              A.md は入力フォームの回答で、
                              あれば依頼文・参考資料をそこから復元する
                              （「フォルダを読み直す」の作り直し用。J.json より優先）
  doctor                      動作に必要なもの（Python の版、claude、Playwright MCP）を
                              確認する。何も変更しない。足りないときは不足を表示し、
                              終了コード 1 で終わる
  cleanup --data D --session-dir S --spec P [--yes]
                              セッション S（D/sessions/ 直下）を削除対象として表示する。
                              --yes を付けたときだけ S を削除する。
                              SPEC（P）がなければ何もしない（承認前は消さない）

質問 JSON:
  {"title": "...", "intro": "...", "questions": [
     {"id": "Q1", "title": "...", "body": "...", "multi": false,
      "options": [{"key": "A", "label": "...", "desc": "..."}],
      "recommended": ["A"], "reason": "..."}]}
final の JSON:
  {"title": "...", "intro": "...", "summary": "（SPEC 案の本文）"}
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import folder_scan

__version__ = "1.2.0"
KEEP_DAYS = 14
MIN_PYTHON = (3, 8)
# 回答に出る節の順と、見出しの次の行の書き出し（本文を持つ節だけ。空は判定しない）
INTAKE_SECTIONS = {
    "更新": "- 読み直し:",
    "依頼文": "- 種別:",
    "保留の依頼文": "- 種別:",
    "参考資料": "",
}
TEMPLATE = Path(__file__).with_name("grill_form_template.html")
INVALID = re.compile(r'[\\/:*?"<>|\s]+')


def data_dir(value: str) -> Path:
    # argparse の type=。置き場（--data）は空文字を受け付けない
    if not value:
        raise argparse.ArgumentTypeError("空のパスは指定できません")
    return Path(value).resolve()


def sessions_root(data: Path) -> Path:
    return data / "sessions"


def newest_file(d: Path) -> Path | None:
    # d 直下（再帰なし）で最も新しいファイル
    # 消えた・読めないファイルは飛ばす
    best, best_time = None, -1.0
    try:
        files = list(d.iterdir())
    except OSError:
        return None
    for f in files:
        try:
            if not f.is_file():
                continue
            t = f.stat().st_mtime
        except OSError:
            continue
        if t > best_time:
            best, best_time = f, t
    return best


def mtime_of(d: Path, newest: Path | None) -> float:
    # セッションの更新時刻。直下のファイルの最新。なければフォルダ自身。
    # 読めないときは新しい扱いにする（読めないものを、古いと見て消さない）
    try:
        return (newest or d).stat().st_mtime
    except OSError:
        return time.time()


def session_mtime(d: Path) -> float:
    return mtime_of(d, newest_file(d))


def prune_old(root: Path) -> None:
    # 古いセッションを削除する（中断したセッションの掃除）
    limit = time.time() - KEEP_DAYS * 86400
    if not root.is_dir():
        return
    for d in root.iterdir():
        if d.is_dir() and session_mtime(d) < limit:
            shutil.rmtree(d, ignore_errors=True)
            if d.exists():
                # 開いているファイルなどで消せない。一覧は変えず、標準エラーに知らせる
                print(f"古いセッションを削除できません: {d}", file=sys.stderr)


def one_line(text: str) -> str:
    return re.sub(r"[\t\r\n]", " ", text)


def read_info(d: Path) -> dict:
    # session.json を読む。なければ・壊れていれば空の辞書
    try:
        info = json.loads((d / "session.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return info if isinstance(info, dict) else {}


def belongs_here(info: dict) -> bool:
    # 別の作業フォルダで始めたセッションは、再開の一覧に出さない。
    # 作業フォルダを読めないセッションは、安全側で出す
    cwd = info.get("cwd")
    if not isinstance(cwd, str):
        return True
    return os.path.normcase(str(Path(cwd))) == os.path.normcase(
        str(Path.cwd().resolve())
    )


def describe_session(
    d: Path, info: dict, newest: Path | None, mtime: float
) -> tuple[str, str, str, str]:
    # (フォルダ名, テーマ, 更新日時, 最新のファイル名)
    theme = info.get("theme")
    return (
        one_line(d.name),
        one_line(theme if isinstance(theme, str) else "(不明)"),
        datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M"),
        one_line(newest.name) if newest else "(なし)",
    )


def normalize_theme(theme: str) -> str:
    return INVALID.sub("-", theme).strip("-") or "untitled"


def spec_path(theme: str, today: datetime.date | None = None) -> Path:
    # 作業フォルダ基準で SPEC のパスを決める。既存のファイルは上書きしない
    base = Path.cwd() / "docs" / "grill-form" / "specs"
    day = (today or datetime.date.today()).isoformat()
    stem = f"{day}-{normalize_theme(theme)}-design"
    cand, n = base / f"{stem}.md", 2
    while cand.exists():
        cand = base / f"{stem}-{n}.md"
        n += 1
    return cand


def cmd_init(args) -> int:
    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
    root = sessions_root(args.data)
    root.mkdir(parents=True, exist_ok=True)
    # 同じテーマを同じ分に呼んでも、別のフォルダにする
    tmp = tempfile.mkdtemp(prefix=f"{stamp}_{normalize_theme(args.theme)}_", dir=root)
    info = {
        "theme": args.theme,
        "created": datetime.datetime.now().isoformat(),
        "cwd": str(Path.cwd().resolve()),
    }
    (Path(tmp) / "session.json").write_text(
        json.dumps(info, ensure_ascii=False), encoding="utf-8"
    )
    print(tmp)
    return 0


def cmd_list(args) -> int:
    root = sessions_root(args.data)
    prune_old(root)
    if not root.is_dir():
        return 0
    found = []
    for d in root.iterdir():
        if not d.is_dir():
            continue
        info = read_info(d)
        if not belongs_here(info):
            continue
        newest = newest_file(d)
        mtime = mtime_of(d, newest)
        found.append((mtime, describe_session(d, info, newest, mtime)))
    for _, row in sorted(found, key=lambda r: r[0], reverse=True):
        print("\t".join(row))
    return 0


def cmd_spec_path(args) -> int:
    path = spec_path(args.theme)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"保存先のフォルダを作れません: {path.parent} ({e})", file=sys.stderr)
        return 1
    print(path)
    return 0


def parse_intake_answers(md: str) -> dict:
    # 入力フォームの回答 Markdown を、フォームの状態に戻せる辞書にする
    state: dict = {
        "refresh": False,
        "kind": "text",
        "request": "",
        "request_file": "",
        "paths": [],
    }
    lines = md.splitlines()
    sections: dict[str, list[str]] = {}
    end = len(lines)
    # 依頼文の本文に「## 参考資料」などの同じ行があっても読めるよう、節は後ろから探す。
    # 本文を持つ節（更新・依頼文・保留の依頼文）は、見出しの次の行でも見分ける
    for name, follow in reversed(INTAKE_SECTIONS.items()):
        for i in range(end - 1, -1, -1):
            if (
                lines[i].startswith("## ")
                and lines[i][3:].strip() == name
                and "\n".join(lines[i + 1 : i + 2]).startswith(follow)
            ):
                sections[name] = lines[i + 1 : end]
                end = i
                break
    state["refresh"] = "更新" in sections
    # 「保留の依頼文」は、選ばれていない側（読み直しで消えないよう退避した入力）
    for key in ("保留の依頼文", "依頼文"):
        body = sections.get(key, [])
        if body and body[0].strip() == "- 種別: ファイル":
            if key == "依頼文":
                state["kind"] = "file"
            state["request_file"] = next(
                (ln.strip().strip('"').strip() for ln in body[1:] if ln.strip()), ""
            )
        elif body:
            state["request"] = "\n".join(body[1:]).strip()
    state["paths"] = [
        ln[2:].strip().strip('"').strip()
        for ln in sections.get("参考資料", [])
        if ln.startswith("- ") and ln[2:].strip()
    ]
    return state


def embed(data: dict) -> str:
    # <script> 内に埋め込むため、< と行区切り文字を無害化する
    # （< を残すと、<!-- のあとの <script で、ブラウザが終了タグを見失う）
    text = json.dumps(data, ensure_ascii=False)
    return (
        text.replace("<", "\\u003c")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def read_payload(path: str) -> dict:
    # --input の JSON（オブジェクト）を読む。読めなければ ValueError（理由つき）
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as e:
        raise ValueError(f"{path} を読めません ({e})") from e
    except ValueError as e:
        raise ValueError(f"{path} は JSON として読めません ({e})") from e
    if not isinstance(payload, dict):
        raise ValueError(f"{path} の JSON は、オブジェクト（{{...}}）にしてください")
    return payload


def cmd_render(args) -> int:
    if not args.intake and (args.round is None or not args.input):
        print("--round と --input が必要です（--intake を除く）。", file=sys.stderr)
        return 2
    try:
        payload = read_payload(args.input) if args.input else {}
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2
    d = Path(args.session_dir)
    d.mkdir(parents=True, exist_ok=True)
    if args.intake:
        if args.answers:
            state = parse_intake_answers(Path(args.answers).read_text(encoding="utf-8"))
            state.pop("refresh")
            # 空の欄は、--input の初期値を消さない
            payload.update({k: v for k, v in state.items() if k == "kind" or v})
        payload["mode"] = "intake"
        payload["round"] = 0
        payload["cwd"] = str(Path.cwd())
        payload["tree"] = folder_scan.scan(Path.cwd())
        payload.setdefault("kind", "text")
        payload.setdefault("title", "入力（依頼文・参考資料）")
        out = d / "intake.html"
    else:
        payload["round"] = args.round
        payload["mode"] = "final" if args.final else "round"
        if not payload.get("title"):
            payload["title"] = (
                f"最終確認（第{args.round}版）"
                if args.final
                else f"ラウンド {args.round}"
            )
        out = d / (
            f"final-{args.round}.html" if args.final else f"round-{args.round}.html"
        )
    payload["session"] = d.name
    html = TEMPLATE.read_text(encoding="utf-8").replace("__DATA__", embed(payload))
    out.write_text(html, encoding="utf-8")
    print(out)
    return 0


def cmd_cleanup(args) -> int:
    d = Path(args.session_dir).resolve()
    # セッション以外（プロジェクト内など）は消さない。
    # init が必ず作る session.json で、本物のセッションだけを対象にする
    if (
        os.path.normcase(str(d.parent))
        != os.path.normcase(str(sessions_root(args.data)))
        or not (d / "session.json").is_file()
    ):
        print(
            f"{d} はセッションではないため何もしません。",
            file=sys.stderr,
        )
        return 1
    spec = Path(args.spec)
    if not spec.is_file() or spec.stat().st_size == 0:
        print(
            "SPEC がない、または空のため何もしません（承認前は削除しません）。",
            file=sys.stderr,
        )
        return 1
    if not d.is_dir():
        print("削除対象はありません。")
        return 0
    print(f"削除対象{'' if args.yes else '（--yes で削除）'}: {d}")
    if args.yes:
        try:
            shutil.rmtree(d)
        except OSError as e:
            print(
                f"削除できませんでした: {e}\n"
                "シェルのカレントフォルダがセッション内にないか確認してください。"
                "SPEC は保存済みです。",
                file=sys.stderr,
            )
            return 1
        print("削除しました。SPEC は残っています。")
    return 0


def mcp_get(claude: str) -> str | None:
    # 登録されていれば claude mcp get の出力、なければ None
    # claude mcp get は MCP サーバーへ実際に接続するので、待ち続けないよう時間を区切る
    try:
        r = subprocess.run(  # noqa: S603 固定の引数で claude を呼ぶ
            [claude, "mcp", "get", "playwright"],
            capture_output=True,
            check=False,
            timeout=30,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    return None if r.returncode else r.stdout.decode("utf-8", "replace")


def cmd_doctor(args) -> int:
    ng = []
    if sys.version_info < MIN_PYTHON:
        ng.append(f"Python {'.'.join(map(str, MIN_PYTHON))} 以上が必要です。")
    claude = shutil.which("claude")
    if claude is None:
        ng.append(
            "claude コマンドが見つかりません（Playwright MCP の確認に使います）。"
        )
    else:
        mcp = mcp_get(claude)
        if mcp is None:
            ng.append(
                "Playwright MCP を確認できません。"
                "`playwright` の名前で登録されていないか、"
                "応答がありません（README の導入方法の手順 3）。"
            )
        elif "--allow-unrestricted-file-access" not in mcp:
            ng.append(
                "Playwright MCP に --allow-unrestricted-file-access が付いていません。"
                "`file://` のフォームが開けません（README の困ったとき）。"
            )
    for msg in ng:
        print(f"NG: {msg}")
    if not ng:
        print("OK: 動作に必要なものはそろっています。")
    return 1 if ng else 0


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--version", action="version", version=f"grill-form {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init")
    p.add_argument("--theme", required=True)
    p.add_argument("--data", required=True, type=data_dir)
    p.set_defaults(fn=cmd_init)

    p = sub.add_parser("list")
    p.add_argument("--data", required=True, type=data_dir)
    p.set_defaults(fn=cmd_list)

    p = sub.add_parser("spec-path")
    p.add_argument("--theme", required=True)
    p.set_defaults(fn=cmd_spec_path)

    p = sub.add_parser("render")
    p.add_argument("--session-dir", required=True)
    p.add_argument("--round", type=int)
    p.add_argument("--final", action="store_true")
    p.add_argument(
        "--intake", action="store_true", help="入力フォーム intake.html を生成する"
    )
    p.add_argument("--input")
    p.add_argument(
        "--answers", help="入力フォームの回答（intake.answers.md）。状態を復元する"
    )
    p.set_defaults(fn=cmd_render)

    p = sub.add_parser("doctor")
    p.set_defaults(fn=cmd_doctor)

    p = sub.add_parser("cleanup")
    p.add_argument("--data", required=True, type=data_dir)
    p.add_argument("--session-dir", required=True)
    p.add_argument(
        "--spec", required=True, help="承認済み SPEC のパス（spec-path の出力）"
    )
    p.add_argument("--yes", action="store_true", help="一覧だけでなく実際に削除する")
    p.set_defaults(fn=cmd_cleanup)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
