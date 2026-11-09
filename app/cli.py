"""コマンドライン（cron での定期収集などに使う）。

例:
  python -m app.cli collect crowdworks "Python" --pages 2
  python -m app.cli watch add coconala "ロゴ作成"
  python -m app.cli watch run          # ウォッチリストを一括収集
  python -m app.cli import service data.csv --platform coconala --keyword ロゴ
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import db
from .importer import import_csv
from .service import add_watch, collect, collect_watchlist


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="app.cli", description="クラウドソーシング調査ツール")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("collect", help="キーワードで検索して保存")
    c.add_argument("platform", choices=["crowdworks", "coconala"])
    c.add_argument("keyword")
    c.add_argument("--pages", type=int, default=1)

    w = sub.add_parser("watch", help="ウォッチリスト操作")
    wsub = w.add_subparsers(dest="wcmd", required=True)
    wa = wsub.add_parser("add")
    wa.add_argument("platform", choices=["crowdworks", "coconala"])
    wa.add_argument("keyword")
    wa.add_argument("--pages", type=int, default=1)
    wsub.add_parser("list")
    wsub.add_parser("run")

    i = sub.add_parser("import", help="CSV を取り込む")
    i.add_argument("kind", choices=["job", "service"])
    i.add_argument("file", type=Path)
    i.add_argument("--platform", default="manual")
    i.add_argument("--keyword", default="")

    args = p.parse_args(argv)
    conn = db.connect()
    if args.cmd == "collect":
        out = collect(conn, args.platform, args.keyword, args.pages)
    elif args.cmd == "watch":
        if args.wcmd == "add":
            add_watch(conn, args.platform, args.keyword, args.pages)
            out = {"added": [args.platform, args.keyword]}
        elif args.wcmd == "list":
            out = [dict(r) for r in conn.execute("SELECT * FROM watchlist")]
        else:
            out = collect_watchlist(conn)
    else:
        out = import_csv(conn, args.file.read_text(encoding="utf-8-sig"), args.kind,
                         args.platform, args.keyword)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
