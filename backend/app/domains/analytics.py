from fastapi import APIRouter, HTTPException, Depends, Query

from ..db import db
from ..providers import analytics_store
from .workspace import get_current_workspace

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


async def _link_flt(link_id: str, ws: dict) -> dict:
    link = await db.links.find_one({"id": link_id, "workspace_id": ws["id"]})
    if not link:
        raise HTTPException(status_code=404, detail="Not found")
    return {"link_id": link_id}


@router.get("/overview")
async def overview(ws=Depends(get_current_workspace)):
    flt = {"workspace_id": ws["id"], "event_type": "click"}
    total_clicks = await analytics_store.count(flt)
    unique = await analytics_store.unique_visitors(flt)
    bot_clicks = await analytics_store.count({**flt, "is_bot": True})
    active_links = await db.links.count_documents({"workspace_id": ws["id"], "status": "active"})
    total_links = await db.links.count_documents({"workspace_id": ws["id"]})
    timeseries = await analytics_store.timeseries(flt)
    top_countries = await analytics_store.breakdown(flt, "country", 5)
    top_devices = await analytics_store.breakdown(flt, "device", 5)

    # top links
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

    return {
        "total_clicks": total_clicks,
        "unique_visitors": unique,
        "bot_clicks": bot_clicks,
        "human_clicks": total_clicks - bot_clicks,
        "active_links": active_links,
        "total_links": total_links,
        "timeseries": timeseries,
        "top_countries": top_countries,
        "top_devices": top_devices,
        "top_links": top_links,
    }


@router.get("/links/{link_id}")
async def link_analytics(link_id: str, ws=Depends(get_current_workspace)):
    flt = await _link_flt(link_id, ws)
    total = await analytics_store.count(flt)
    unique = await analytics_store.unique_visitors(flt)
    bots = await analytics_store.count({**flt, "is_bot": True})
    return {
        "total_clicks": total,
        "unique_visitors": unique,
        "bot_clicks": bots,
        "human_clicks": total - bots,
        "timeseries": await analytics_store.timeseries(flt),
        "countries": await analytics_store.breakdown(flt, "country", 10),
        "devices": await analytics_store.breakdown(flt, "device", 10),
        "browsers": await analytics_store.breakdown(flt, "browser", 10),
        "referrers": await analytics_store.breakdown(flt, "referrer", 10),
        "recent": await analytics_store.recent(flt, 20),
    }
