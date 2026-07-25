"""Agrégats pour les graphiques auto-générés et la carte."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.services import aggregation

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/summary")
def summary(
    zone: str | None = None,
    period_start: str | None = None,
    period_end: str | None = None,
    db: Session = Depends(get_db),
):
    """Vue d'ensemble : sites, incidents, stocks, indicateurs pour une zone."""
    return {
        "sites": aggregation.count_sites(db, zone=zone),
        "incidents": aggregation.incidents_summary(
            db, zone=zone, period_start=period_start, period_end=period_end
        ),
        "stocks": aggregation.stock_summary(
            db, zone=zone, period_start=period_start, period_end=period_end
        ),
        "catalog": aggregation.catalog(db),
    }


@router.get("/indicator")
def indicator(
    name: str,
    zone: str | None = None,
    period_start: str | None = None,
    period_end: str | None = None,
    db: Session = Depends(get_db),
):
    return aggregation.indicator_series(
        db, name=name, zone=zone, period_start=period_start, period_end=period_end
    )


@router.get("/map")
def map_stats(
    metric: str = "sites",
    site_type: str | None = None,
    status: str | None = None,
    incident_type: str | None = None,
    name: str | None = None,
    resource: str | None = None,
    period_start: str | None = None,
    period_end: str | None = None,
    db: Session = Depends(get_db),
):
    """Valeurs par région pour la choroplèthe de la carte."""
    return aggregation.map_stats(
        db,
        metric,
        site_type=site_type,
        status=status,
        incident_type=incident_type,
        name=name,
        resource=resource,
        period_start=period_start,
        period_end=period_end,
    )
