"""Web アプリ本体（FastAPI）。起動: uvicorn app.main:app --reload"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import analysis, db
from .collectors.base import FetchError
from .importer import import_csv, to_csv
from .service import add_watch, collect, collect_watchlist

STATIC = Path(__file__).parent / "static"

app = FastAPI(title="クラウドソーシング調査ツール")
app.mount("/static", StaticFiles(directory=STATIC), name="static")

_conn = None


def get_conn():
    global _conn
    if _conn is None:
        _conn = db.connect()
    return _conn


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html")


# --- 収集 -----------------------------------------------------------------
class CollectRequest(BaseModel):
    platform: str
    keyword: str
    pages: int = Field(1, ge=1, le=10)


@app.post("/api/collect")
def api_collect(req: CollectRequest, conn=Depends(get_conn)):
    try:
        return collect(conn, req.platform, req.keyword, req.pages)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except FetchError as e:
        raise HTTPException(502, str(e))


@app.get("/api/watchlist")
def api_watchlist(conn=Depends(get_conn)):
    return [dict(r) for r in conn.execute("SELECT * FROM watchlist ORDER BY id")]


@app.post("/api/watchlist")
def api_watch_add(req: CollectRequest, conn=Depends(get_conn)):
    try:
        add_watch(conn, req.platform, req.keyword, req.pages)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


@app.delete("/api/watchlist/{watch_id}")
def api_watch_delete(watch_id: int, conn=Depends(get_conn)):
    conn.execute("DELETE FROM watchlist WHERE id = ?", (watch_id,))
    conn.commit()
    return {"ok": True}


@app.post("/api/watchlist/run")
def api_watch_run(conn=Depends(get_conn)):
    return collect_watchlist(conn)


# --- 参照・分析 -------------------------------------------------------------
@app.get("/api/overview")
def api_overview(conn=Depends(get_conn)):
    return {**analysis.overview(conn), "keywords": analysis.keywords(conn)}


@app.get("/api/jobs")
def api_jobs(keyword: str = "", platform: str = "", payment_type: str = "", q: str = "",
             min_budget: Optional[float] = None, sort: str = "new", limit: int = 200,
             conn=Depends(get_conn)):
    return analysis.list_jobs(conn, keyword, platform, payment_type, min_budget, q, sort, limit)


@app.get("/api/services")
def api_services(keyword: str = "", platform: str = "", q: str = "", seller: str = "",
                 sort: str = "reviews", limit: int = 200, conn=Depends(get_conn)):
    return analysis.list_services(conn, keyword, platform, q, seller, sort, limit)


@app.get("/api/stats/prices")
def api_prices(kind: str = "service", keyword: str = "", platform: str = "",
               payment_type: str = "fixed", conn=Depends(get_conn)):
    if kind not in ("job", "service"):
        raise HTTPException(400, "kind は job か service")
    return analysis.price_stats(conn, kind, keyword, platform, payment_type)


@app.get("/api/stats/trends")
def api_trends(keyword: str = "", platform: str = "", conn=Depends(get_conn)):
    return analysis.trends(conn, keyword, platform)


@app.get("/api/stats/sellers")
def api_sellers(keyword: str = "", platform: str = "", days: int = 30, conn=Depends(get_conn)):
    return analysis.seller_ranking(conn, keyword, platform, days)


@app.get("/api/stats/clients")
def api_clients(keyword: str = "", platform: str = "", conn=Depends(get_conn)):
    return analysis.client_ranking(conn, keyword, platform)


# --- 取り込み・書き出し -------------------------------------------------------
@app.post("/api/import")
async def api_import(kind: str = Form(...), file: UploadFile = File(...), platform: str = Form("manual"),
                     keyword: str = Form(""), conn=Depends(get_conn)):
    if kind not in ("job", "service"):
        raise HTTPException(400, "kind は job か service")
    raw = await file.read()
    for enc in ("utf-8-sig", "cp932"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise HTTPException(400, "文字コードを判別できません（UTF-8 か Shift_JIS で保存してください）")
    return import_csv(conn, text, kind, platform or "manual", keyword)


@app.get("/api/export")
def api_export(kind: str = "service", keyword: str = "", platform: str = "", conn=Depends(get_conn)):
    if kind == "job":
        rows = analysis.list_jobs(conn, keyword, platform, limit=100000)
    elif kind == "service":
        rows = analysis.list_services(conn, keyword, platform, limit=100000)
    elif kind == "sellers":
        rows = analysis.seller_ranking(conn, keyword, platform, limit=100000)
    else:
        raise HTTPException(400, "kind は job / service / sellers")
    return Response(to_csv(rows), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{kind}.csv"'})
