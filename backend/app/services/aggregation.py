"""Fonctions d'agrégation partagées par les dashboards et le RAG.

Ce sont les SEULES portes d'accès aux données pour le LLM : il ne génère
jamais de SQL. Toutes les réponses sont agrégées (comptages, sommes,
séries temporelles par zone) — jamais de détail individuel.
"""
from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import AdminZone, Incident, Indicator, Site, Stock
from app.services.zone_matcher import (
    ZoneMatcher,
    normalize,
    zone_with_descendants_ids,
)


def _zone_filter(db: Session, query, model, zone_name: str | None):
    """Applique un filtre de zone (nom en français, tout niveau). Retourne
    (query, zone, erreur)."""
    if not zone_name:
        return query, None, None
    zone = ZoneMatcher(db).match(zone_name)
    if zone is None:
        return query, None, f"Zone inconnue : « {zone_name} »"
    ids = zone_with_descendants_ids(db, zone.id)
    return query.filter(model.zone_id.in_(ids)), zone, None


def _period_filter(query, model, period_start: str | None, period_end: str | None):
    if period_start:
        query = query.filter(
            func.coalesce(model.period_end, model.period_start)
            >= date.fromisoformat(period_start)
        )
    if period_end:
        query = query.filter(model.period_start <= date.fromisoformat(period_end))
    return query


def _region_index(db: Session) -> dict[int, str]:
    """zone_id → nom de la région ancêtre (pour les regroupements)."""
    zones = {z.id: z for z in db.query(AdminZone).all()}
    index: dict[int, str] = {}
    for zid, zone in zones.items():
        current = zone
        while current.parent_id is not None and current.level != "region":
            current = zones[current.parent_id]
        index[zid] = current.name if current.level == "region" else zone.name
    return index


def count_sites(
    db: Session,
    site_type: str | None = None,
    status: str | None = None,
    zone: str | None = None,
) -> dict:
    """Compte les sites (filtres : type, état fonctionnel, zone)."""
    q = db.query(Site)
    if site_type:
        q = q.filter(Site.site_type.ilike(f"%{normalize(site_type)}%"))
    if status:
        q = q.filter(Site.status == normalize(status))
    q, zone_obj, err = _zone_filter(db, q, Site, zone)
    if err:
        return {"error": err}
    sites = q.all()
    by_status: dict[str, int] = {}
    by_type: dict[str, int] = {}
    region_of = _region_index(db)
    by_region: dict[str, int] = {}
    for s in sites:
        by_status[s.status] = by_status.get(s.status, 0) + 1
        by_type[s.site_type] = by_type.get(s.site_type, 0) + 1
        r = region_of.get(s.zone_id, "?")
        by_region[r] = by_region.get(r, 0) + 1
    return {
        "total": len(sites),
        "zone": zone_obj.name if zone_obj else "Niger (tout le pays)",
        "by_status": by_status,
        "by_type": by_type,
        "by_region": by_region,
    }


def indicator_series(
    db: Session,
    name: str | None = None,
    zone: str | None = None,
    period_start: str | None = None,
    period_end: str | None = None,
) -> dict:
    """Série temporelle et total d'un indicateur agrégé."""
    q = db.query(
        Indicator.period_start,
        func.sum(Indicator.value),
        func.count(Indicator.id),
        Indicator.unit,
    )
    if name:
        q = q.filter(Indicator.name.ilike(f"%{normalize(name)}%"))
    q, zone_obj, err = _zone_filter(db, q, Indicator, zone)
    if err:
        return {"error": err}
    q = _period_filter(q, Indicator, period_start, period_end)
    rows = (
        q.group_by(Indicator.period_start, Indicator.unit)
        .order_by(Indicator.period_start)
        .all()
    )
    series = [
        {
            "period": p.isoformat() if p else None,
            "value": float(v or 0),
            "records": int(n),
        }
        for p, v, n, _ in rows
    ]
    return {
        "indicator": name or "tous",
        "zone": zone_obj.name if zone_obj else "Niger (tout le pays)",
        "unit": rows[0][3] if rows else None,
        "total": round(sum(s["value"] for s in series), 3),
        "series": series,
    }


def stock_summary(
    db: Session,
    resource: str | None = None,
    zone: str | None = None,
    period_start: str | None = None,
    period_end: str | None = None,
) -> dict:
    """Totaux et série temporelle des stocks (par ressource)."""
    q = db.query(Stock)
    if resource:
        q = q.filter(Stock.resource_name.ilike(f"%{normalize(resource)}%"))
    q, zone_obj, err = _zone_filter(db, q, Stock, zone)
    if err:
        return {"error": err}
    q = _period_filter(q, Stock, period_start, period_end)
    stocks = q.order_by(Stock.period_start).all()
    by_resource: dict[str, dict] = {}
    series: dict[str, float] = {}
    for s in stocks:
        entry = by_resource.setdefault(
            s.resource_name, {"quantity": 0.0, "unit": s.unit}
        )
        entry["quantity"] = round(entry["quantity"] + float(s.quantity), 3)
        key = s.period_start.isoformat() if s.period_start else "sans période"
        series[key] = round(series.get(key, 0.0) + float(s.quantity), 3)
    return {
        "resource": resource or "toutes",
        "zone": zone_obj.name if zone_obj else "Niger (tout le pays)",
        "records": len(stocks),
        "by_resource": by_resource,
        "series": [
            {"period": k, "quantity": v} for k, v in sorted(series.items())
        ],
    }


def incidents_summary(
    db: Session,
    incident_type: str | None = None,
    zone: str | None = None,
    period_start: str | None = None,
    period_end: str | None = None,
) -> dict:
    """Fréquence d'incidents agrégés par zone, type et période."""
    q = db.query(Incident)
    if incident_type:
        q = q.filter(Incident.incident_type.ilike(f"%{normalize(incident_type)}%"))
    q, zone_obj, err = _zone_filter(db, q, Incident, zone)
    if err:
        return {"error": err}
    q = _period_filter(q, Incident, period_start, period_end)
    incidents = q.all()
    region_of = _region_index(db)
    by_type: dict[str, int] = {}
    by_region: dict[str, int] = {}
    series: dict[str, int] = {}
    total = 0
    for i in incidents:
        total += i.count
        by_type[i.incident_type] = by_type.get(i.incident_type, 0) + i.count
        r = region_of.get(i.zone_id, "?")
        by_region[r] = by_region.get(r, 0) + i.count
        if i.period_start:
            key = i.period_start.replace(day=1).isoformat()
            series[key] = series.get(key, 0) + i.count
    return {
        "incident_type": incident_type or "tous",
        "zone": zone_obj.name if zone_obj else "Niger (tout le pays)",
        "total": total,
        "by_type": by_type,
        "by_region": by_region,
        "series": [{"period": k, "count": v} for k, v in sorted(series.items())],
    }


def catalog(db: Session) -> dict:
    """Ce qui existe en base : types de sites, indicateurs, ressources,
    types d'incidents. Sert au frontend et au contexte du LLM."""
    return {
        "site_types": [r[0] for r in db.query(Site.site_type).distinct().all()],
        "site_statuses": [r[0] for r in db.query(Site.status).distinct().all()],
        "indicators": [r[0] for r in db.query(Indicator.name).distinct().all()],
        "resources": [r[0] for r in db.query(Stock.resource_name).distinct().all()],
        "incident_types": [
            r[0] for r in db.query(Incident.incident_type).distinct().all()
        ],
    }


def map_stats(db: Session, metric: str, **filters) -> dict:
    """Valeur par région pour la choroplèthe.

    metric : "sites" | "incidents" | "indicator" | "stocks"
    """
    if metric == "sites":
        data = count_sites(db, site_type=filters.get("site_type"),
                           status=filters.get("status"))
        return {"metric": metric, "by_region": data["by_region"]}
    if metric == "incidents":
        data = incidents_summary(
            db,
            incident_type=filters.get("incident_type"),
            period_start=filters.get("period_start"),
            period_end=filters.get("period_end"),
        )
        return {"metric": metric, "by_region": data["by_region"]}
    region_of = _region_index(db)
    by_region: dict[str, float] = {}
    if metric == "indicator":
        q = db.query(Indicator.zone_id, func.sum(Indicator.value))
        if filters.get("name"):
            q = q.filter(Indicator.name.ilike(f"%{normalize(filters['name'])}%"))
        q = _period_filter(q, Indicator, filters.get("period_start"),
                           filters.get("period_end"))
        for zid, value in q.group_by(Indicator.zone_id).all():
            r = region_of.get(zid, "?")
            by_region[r] = round(by_region.get(r, 0.0) + float(value or 0), 3)
    elif metric == "stocks":
        q = db.query(Stock.zone_id, func.sum(Stock.quantity))
        if filters.get("resource"):
            q = q.filter(Stock.resource_name.ilike(f"%{normalize(filters['resource'])}%"))
        q = _period_filter(q, Stock, filters.get("period_start"),
                           filters.get("period_end"))
        for zid, value in q.group_by(Stock.zone_id).all():
            r = region_of.get(zid, "?")
            by_region[r] = round(by_region.get(r, 0.0) + float(value or 0), 3)
    return {"metric": metric, "by_region": by_region}
