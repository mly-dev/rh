"""Consultation des objets métier (listes filtrables) et de l'ontologie."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models import Incident, Indicator, Site, Stock
from app.ontology import ENTITIES
from app.services import aggregation
from app.services.zone_matcher import ZoneMatcher, zone_with_descendants_ids

router = APIRouter(prefix="/api", tags=["objets"])

MAX_RESULTS = 1000


def _zone_ids(db: Session, zone: str | None) -> list[int] | None:
    if not zone:
        return None
    matched = ZoneMatcher(db).match(zone)
    if matched is None:
        return []
    return zone_with_descendants_ids(db, matched.id)


@router.get("/ontology")
def get_ontology():
    """Le registre des objets métier (pilote l'éditeur de mapping)."""
    return ENTITIES


@router.get("/catalog")
def get_catalog(db: Session = Depends(get_db)):
    """Types, indicateurs et ressources présents en base (pour les filtres)."""
    return aggregation.catalog(db)


@router.get("/sites")
def list_sites(
    zone: str | None = None,
    site_type: str | None = None,
    status: str | None = None,
    limit: int = Query(500, le=MAX_RESULTS),
    db: Session = Depends(get_db),
):
    q = db.query(Site)
    ids = _zone_ids(db, zone)
    if ids is not None:
        q = q.filter(Site.zone_id.in_(ids))
    if site_type:
        q = q.filter(Site.site_type.ilike(f"%{site_type.lower()}%"))
    if status:
        q = q.filter(Site.status == status)
    return [
        {
            "id": s.id,
            "name": s.name,
            "site_type": s.site_type,
            "zone": s.zone.name if s.zone else None,
            "lat": s.lat,
            "lon": s.lon,
            "status": s.status,
            "capacity": float(s.capacity) if s.capacity is not None else None,
            "capacity_unit": s.capacity_unit,
            "properties": s.properties,
        }
        for s in q.limit(limit).all()
    ]


@router.get("/stocks")
def list_stocks(
    zone: str | None = None,
    resource: str | None = None,
    limit: int = Query(500, le=MAX_RESULTS),
    db: Session = Depends(get_db),
):
    q = db.query(Stock)
    ids = _zone_ids(db, zone)
    if ids is not None:
        q = q.filter(Stock.zone_id.in_(ids))
    if resource:
        q = q.filter(Stock.resource_name.ilike(f"%{resource.lower()}%"))
    return [
        {
            "id": s.id,
            "resource_name": s.resource_name,
            "category": s.category,
            "quantity": float(s.quantity),
            "unit": s.unit,
            "site": s.site.name if s.site else None,
            "zone": s.zone.name if s.zone else None,
            "period_start": s.period_start.isoformat() if s.period_start else None,
            "period_end": s.period_end.isoformat() if s.period_end else None,
        }
        for s in q.order_by(Stock.period_start).limit(limit).all()
    ]


@router.get("/incidents")
def list_incidents(
    zone: str | None = None,
    incident_type: str | None = None,
    limit: int = Query(500, le=MAX_RESULTS),
    db: Session = Depends(get_db),
):
    q = db.query(Incident)
    ids = _zone_ids(db, zone)
    if ids is not None:
        q = q.filter(Incident.zone_id.in_(ids))
    if incident_type:
        q = q.filter(Incident.incident_type.ilike(f"%{incident_type.lower()}%"))
    return [
        {
            "id": i.id,
            "zone": i.zone.name if i.zone else None,
            "incident_type": i.incident_type,
            "count": i.count,
            "severity": i.severity,
            "period_start": i.period_start.isoformat() if i.period_start else None,
            "period_end": i.period_end.isoformat() if i.period_end else None,
        }
        for i in q.order_by(Incident.period_start).limit(limit).all()
    ]


@router.get("/indicators")
def list_indicators(
    zone: str | None = None,
    name: str | None = None,
    limit: int = Query(500, le=MAX_RESULTS),
    db: Session = Depends(get_db),
):
    q = db.query(Indicator)
    ids = _zone_ids(db, zone)
    if ids is not None:
        q = q.filter(Indicator.zone_id.in_(ids))
    if name:
        q = q.filter(Indicator.name.ilike(f"%{name.lower()}%"))
    return [
        {
            "id": i.id,
            "name": i.name,
            "value": float(i.value),
            "unit": i.unit,
            "zone": i.zone.name if i.zone else None,
            "site": i.site.name if i.site else None,
            "period_start": i.period_start.isoformat() if i.period_start else None,
            "period_end": i.period_end.isoformat() if i.period_end else None,
        }
        for i in q.order_by(Indicator.period_start).limit(limit).all()
    ]
