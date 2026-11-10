"""spec-interview スキル用のスクリプト。

サブコマンド:
  init   --theme T            OS の一時フォルダに作業用フォルダを作り、
                              そのパスを1行で出力する
                              （HTML・回答・質問 JSON を置く。掃除は OS に任せる）
  spec-path --theme T         SPEC の保存先
                              <作業フォルダ>/docs/spec-interview/specs/<日付>-<テーマ>-design.md
                              を決め、フォルダを作って、パスを出力する
                              （ファイルは作らない）。作業フォルダは、
                              このスクリプトのカレントフォルダ。
                              同名のファイルがあれば末尾に連番を付ける
  render --session-dir D --round N [--final] --input J.json
                              質問 JSON から round-N.html を生成し、パスを出力する。
                              --final のときは N を最終確認の版番号とし、
                              final-N.html を生成する
                              （修正のたびに版を上げ、前の版を上書きしない）
  doctor                      動作に必要なもの（Python の版、claude、Playwright MCP）を
                              確認する。何も変更しない。足りないときは不足を表示し、
                              終了コード 1 で終わる。あわせて現在の版を表示し、
                              GitHub をマーケットプレイスに登録していれば、
                              最新版かも確認する（更新があっても終了コードは 0）

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
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

__version__ = "1.0.0"
MIN_PYTHON = (3, 8)
REPO = "asama0101/spec-interview"
LATEST_URL = (
    f"https://raw.githubusercontent.com/{REPO}/main"
    "/plugins/spec-interview/.claude-plugin/plugin.json"
)
KNOWN_MARKETPLACES = Path.home() / ".claude" / "plugins" / "known_marketplaces.json"
TEMPLATE = Path(__file__).with_name("spec_interview_template.html")
INVALID = re.compile(r'[\\/:*?"<>|\s]+')


def normalize_theme(theme: str) -> str:
    return INVALID.sub("-", theme).strip("-") or "untitled"


def spec_path(theme: str, today: datetime.date | None = None) -> Path:
    # 作業フォルダ基準で SPEC のパスを決める。既存のファイルは上書きしない
    base = Path.cwd() / "docs" / "spec-interview" / "specs"
    day = (today or datetime.date.today()).isoformat()
    stem = f"{day}-{normalize_theme(theme)}-design"
    cand, n = base / f"{stem}.md", 2
    while cand.exists():
        cand = base / f"{stem}-{n}.md"
        n += 1
    return cand


def cmd_init(args) -> int:
    # 作業ファイルは OS の一時フォルダに置く。掃除は OS に任せる
    print(tempfile.mkdtemp(prefix=f"spec-interview_{normalize_theme(args.theme)}_"))
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


def embed(data: dict) -> str:
    # <script> 内に埋め込むため、< と行区切り文字を無害化する
    # （< を残すと、<!-- のあとの <script で、ブラウザが終了タグを見失う）
    text = json.dumps(data, ensure_ascii=False)
    return (
        text.replace("<", "\\u003c")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def read_text(path: str) -> str:
    # 読めなければ ValueError（理由つき）。コマンドの入力ファイルに使う
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, ValueError) as e:
        raise ValueError(f"{path} を読めません ({e})") from e


def read_payload(path: str) -> dict:
    # --input の JSON（オブジェクト）を読む。読めなければ ValueError（理由つき）
    text = read_text(path)
    try:
        payload = json.loads(text)
    except ValueError as e:
        raise ValueError(f"{path} は JSON として読めません ({e})") from e
    if not isinstance(payload, dict):
        raise ValueError(f"{path} の JSON は、オブジェクト（{{...}}）にしてください")
    return payload


def cmd_render(args) -> int:
    if args.round is None or not args.input:
        print("--round と --input が必要です。", file=sys.stderr)
        return 2
    try:
        payload = read_payload(args.input)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2
    d = Path(args.session_dir)
    d.mkdir(parents=True, exist_ok=True)
    payload["round"] = args.round
    payload["mode"] = "final" if args.final else "round"
    if not payload.get("title"):
        payload["title"] = (
            f"最終確認（第{args.round}版）" if args.final else f"ラウンド {args.round}"
        )
    out = d / (f"final-{args.round}.html" if args.final else f"round-{args.round}.html")
    payload["session"] = d.name
    html = TEMPLATE.read_text(encoding="utf-8").replace("__DATA__", embed(payload))
    out.write_text(html, encoding="utf-8")
    print(out)
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


def github_marketplace_registered() -> bool:
    # このリポジトリを GitHub のマーケットプレイスとして登録しているか
    try:
        known = json.loads(KNOWN_MARKETPLACES.read_text(encoding="utf-8"))
        return any(
            m["source"]["source"] == "github" and m["source"]["repo"] == REPO
            for m in known.values()
        )
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return False


def latest_version() -> str | None:
    # GitHub の main にある plugin.json の版。取得できなければ None
    try:
        with urllib.request.urlopen(LATEST_URL, timeout=10) as r:  # noqa: S310 固定の https URL
            version = json.loads(r.read().decode("utf-8"))["version"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return version if isinstance(version, str) else None


def version_key(v: str) -> tuple:
    return tuple(int(n) if n.isdigit() else 0 for n in re.split(r"[.\-+]", v))


def report_version() -> None:
    # 版の案内。更新が必要でも NG にはしない（動作環境の不足ではないため）
    print(f"[情報] 現在の版は {__version__} です。")
    if not github_marketplace_registered():
        print(
            f"[情報] GitHub（{REPO}）をマーケットプレイスに登録していないので、"
            "最新版の確認は省略します。"
        )
        return
    latest = latest_version()
    if latest is None:
        print("[情報] 最新版を確認できませんでした（GitHub に接続できません）。")
    elif version_key(latest) > version_key(__version__):
        print(
            f"[情報] 新しい版 {latest} があります。"
            "`claude plugin marketplace update spec-interview` のあと、"
            "`claude plugin update spec-interview@spec-interview` で更新し、"
            "Claude Code を再起動してください。"
        )
    else:
        print("[情報] 最新版です。")


def cmd_doctor(args) -> int:
    report_version()
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
        print(f"[NG] {msg}")
    if not ng:
        print("[OK] 動作に必要なものはそろっています。")
    return 3 if ng else 0


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--version", action="version", version=f"spec-interview {__version__}"
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init")
    p.add_argument("--theme", required=True)
    p.set_defaults(fn=cmd_init)

    p = sub.add_parser("spec-path")
    p.add_argument("--theme", required=True)
    p.set_defaults(fn=cmd_spec_path)

    p = sub.add_parser("render")
    p.add_argument("--session-dir", required=True)
    p.add_argument("--round", type=int)
    p.add_argument("--final", action="store_true")
    p.add_argument("--input")
    p.set_defaults(fn=cmd_render)

    p = sub.add_parser("doctor")
    p.set_defaults(fn=cmd_doctor)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
