"""Peuplement de la table admin_zones depuis app/data/niger_zones.json."""
import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import AdminZone
from app.services.zone_matcher import normalize

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "niger_zones.json"


def seed_zones(db: Session) -> int:
    """Insère les zones manquantes (idempotent). Retourne le nombre créé."""
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    existing = {
        (z.level, z.normalized_name) for z in db.query(AdminZone).all()
    }
    created = 0

    def add(name: str, level: str, parent: AdminZone | None, code: str | None = None,
            centroid: list | None = None) -> AdminZone:
        nonlocal created
        norm = normalize(name)
        if (level, norm) in existing:
            return (
                db.query(AdminZone)
                .filter_by(level=level, normalized_name=norm)
                .first()
            )
        zone = AdminZone(
            name=name,
            normalized_name=norm,
            level=level,
            parent_id=parent.id if parent else None,
            code=code,
            centroid_lat=centroid[0] if centroid else None,
            centroid_lon=centroid[1] if centroid else None,
        )
        db.add(zone)
        db.flush()
        existing.add((level, norm))
        created += 1
        return zone

    for region in data["regions"]:
        r = add(region["name"], "region", None, region.get("code"), region.get("centroid"))
        for dept in region.get("departments", []):
            d = add(dept["name"], "departement", r)
            for com in dept.get("communes", []):
                add(com["name"], "commune", d, None, com.get("centroid"))

    db.commit()
    return created
