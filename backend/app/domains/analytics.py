import csv
import io
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Depends, Query, Request
from fastapi.responses import StreamingResponse

from ..db import db
from ..providers import analytics_store
from ..security import get_current_user
from .workspace import get_current_workspace, assert_member

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def _range_filter(start: str | None, end: str | None) -> dict:
    f = {}
    if start:
        f["$gte"] = f"{start}T00:00:00+00:00"
    if end:
        f["$lte"] = f"{end}T23:59:59.999999+00:00"
    return {"occurred_at": f} if f else {}


def _prev_range(start: str, end: str) -> tuple[str, str]:
    s = datetime.fromisoformat(start)
    e = datetime.fromisoformat(end)
    span = (e - s).days + 1
    ps = (s - timedelta(days=span)).strftime("%Y-%m-%d")
    pe = (s - timedelta(days=1)).strftime("%Y-%m-%d")
    return ps, pe


async def _base_counts(flt: dict) -> dict:
    total = await analytics_store.count(flt)
    unique = await analytics_store.unique_visitors(flt)
    bots = await analytics_store.count({**flt, "is_bot": True})
    blocked = await analytics_store.count({**flt, "decision": "block"})
    challenged = await analytics_store.count({**flt, "decision": "challenge"})
    return {
        "total_clicks": total,
        "unique_visitors": unique,
        "bot_clicks": bots,
        "human_clicks": total - bots,
        "blocked": blocked,
        "challenged": challenged,
    }


@router.get("/overview")
async def overview(
    ws=Depends(get_current_workspace),
    start: str | None = Query(None),
    end: str | None = Query(None),
    compare: bool = Query(False),
):
    flt = {"workspace_id": ws["id"], **_range_filter(start, end)}
    counts = await _base_counts(flt)
    active_links = await db.links.count_documents({"workspace_id": ws["id"], "status": "active", "is_qr": {"$ne": True}})
    total_links = await db.links.count_documents({"workspace_id": ws["id"], "is_qr": {"$ne": True}})
    active_qr = await db.links.count_documents({"workspace_id": ws["id"], "is_qr": True})

    pipeline = [
        {"$match": flt},
        {"$group": {"_id": "$link_id", "clicks": {"$sum": 1}}},
        {"$sort": {"clicks": -1}},
        {"$limit": 5},
    ]
    rows = await db.analytics_events.aggregate(pipeline).to_list(5)
    top_links = []
    for r in rows:
        link = await db.links.find_one({"id": r["_id"]}, {"_id": 0, "name": 1, "alias": 1})
        if link:
            top_links.append({"name": link["name"], "alias": link["alias"], "clicks": r["clicks"]})

    result = {
        **counts,
        "avg_risk_score": await _avg_risk(flt),
        "active_links": active_links,
        "total_links": total_links,
        "active_qr": active_qr,
        "timeseries": await analytics_store.timeseries(flt),
        "top_countries": await analytics_store.breakdown(flt, "country", 8),
        "top_devices": await analytics_store.breakdown(flt, "device", 5),
        "top_links": top_links,
    }
    if compare and start and end:
        ps, pe = _prev_range(start, end)
        prev_flt = {"workspace_id": ws["id"], **_range_filter(ps, pe)}
        result["previous"] = await _base_counts(prev_flt)
    return result


async def _avg_risk(flt: dict) -> float:
    pipeline = [{"$match": flt}, {"$group": {"_id": None, "avg": {"$avg": "$risk_score"}}}]
    rows = await db.analytics_events.aggregate(pipeline).to_list(1)
    return round(rows[0]["avg"], 1) if rows and rows[0].get("avg") is not None else 0.0


async def _assert_link(link_id: str, ws: dict):
    link = await db.links.find_one({"id": link_id, "workspace_id": ws["id"]})
    if not link:
        raise HTTPException(status_code=404, detail="Not found")
    return link


@router.get("/links/{link_id}")
async def link_analytics(
    link_id: str,
    ws=Depends(get_current_workspace),
    start: str | None = Query(None),
    end: str | None = Query(None),
    compare: bool = Query(False),
):
    await _assert_link(link_id, ws)
    flt = {"link_id": link_id, **_range_filter(start, end)}
    counts = await _base_counts(flt)
    result = {
        **counts,
        "avg_risk_score": await _avg_risk(flt),
        "timeseries": await analytics_store.timeseries(flt),
        "countries": await analytics_store.breakdown(flt, "country", 10),
        "devices": await analytics_store.breakdown(flt, "device", 10),
        "browsers": await analytics_store.breakdown(flt, "browser", 10),
        "referrers": await analytics_store.breakdown(flt, "referrer", 10),
        "decisions": await analytics_store.breakdown(flt, "decision", 10),
        "recent": await analytics_store.recent(flt, 20),
    }
    if compare and start and end:
        ps, pe = _prev_range(start, end)
        result["previous"] = await _base_counts({"link_id": link_id, **_range_filter(ps, pe)})
    return result


@router.get("/links/{link_id}/export.csv")
async def export_link_csv(
    link_id: str,
    request: Request,
    user=Depends(get_current_user),
    start: str | None = Query(None),
    end: str | None = Query(None),
):
    # resolve workspace from the link itself (window.open can't send workspace header)
    link = await db.links.find_one({"id": link_id})
    if not link:
        raise HTTPException(status_code=404, detail="Not found")
    await assert_member(user["id"], link["workspace_id"])

    flt = {"link_id": link_id, **_range_filter(start, end)}
    rows = await db.analytics_events.find(flt, {"_id": 0}).sort("occurred_at", -1).to_list(10000)

    buf = io.StringIO()
    cols = ["occurred_at", "country", "device", "browser", "os", "referrer",
            "is_bot", "risk_score", "decision", "challenge_result", "visitor_id"]
    writer = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        writer.writerow(r)
    buf.seek(0)
    fname = f"midgate_{link['alias']}_clicks.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )
