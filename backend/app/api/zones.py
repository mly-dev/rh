"""Zones administratives : arbre hiérarchique et géométries."""
import json
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models import AdminZone

router = APIRouter(prefix="/api/zones", tags=["zones"])

GEO_DIR = Path(__file__).resolve().parent.parent / "data" / "geo"


@router.get("")
def zone_tree(db: Session = Depends(get_db)) -> list[dict]:
    """Arbre région → départements → communes."""
    zones = db.query(AdminZone).order_by(AdminZone.name).all()
    by_parent: dict[int | None, list[AdminZone]] = {}
    for z in zones:
        by_parent.setdefault(z.parent_id, []).append(z)

    def node(z: AdminZone) -> dict:
        return {
            "id": z.id,
            "name": z.name,
            "level": z.level,
            "code": z.code,
            "centroid": [z.centroid_lat, z.centroid_lon]
            if z.centroid_lat is not None
            else None,
            "children": [node(c) for c in by_parent.get(z.id, [])],
        }

    return [node(z) for z in by_parent.get(None, [])]


@router.get("/geojson")
def zones_geojson(level: str = "region") -> dict:
    """Géométries simplifiées (démo) pour les choroplèthes."""
    path = GEO_DIR / f"{level}s.geojson"
    if not path.exists():
        return {"type": "FeatureCollection", "features": []}
    return json.loads(path.read_text(encoding="utf-8"))
