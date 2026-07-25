"""Rattachement des noms de zones des fichiers aux zones administratives.

Normalisation (accents, casse, apostrophes, tirets) puis correspondance
exacte, et à défaut correspondance floue (difflib). Les lignes sans zone
reconnue sont rejetées à l'import avec un motif explicite — jamais
insérées silencieusement.
"""
import unicodedata
from difflib import get_close_matches

from sqlalchemy.orm import Session

from app.models import AdminZone

# Priorité de résolution quand un même nom existe à plusieurs niveaux :
# on choisit la portée la plus large (une question sur « Tillabéri » vise la
# région, pas la commune) ; les agrégations incluent toute la descendance.
LEVEL_PRIORITY = ("region", "departement", "commune")


def normalize(name: str) -> str:
    if name is None:
        return ""
    s = unicodedata.normalize("NFKD", str(name))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().strip()
    for ch in ("'", "’", "-", "_", "."):
        s = s.replace(ch, " ")
    return " ".join(s.split())


class ZoneMatcher:
    """Index en mémoire des zones (rechargé par instance ; volume faible)."""

    def __init__(self, db: Session):
        self.zones: list[AdminZone] = db.query(AdminZone).all()
        self.by_norm: dict[str, list[AdminZone]] = {}
        for z in self.zones:
            self.by_norm.setdefault(z.normalized_name, []).append(z)

    def match(self, raw_name: str, level: str | None = None) -> AdminZone | None:
        """Retourne la zone correspondante, ou None si aucune n'est fiable."""
        norm = normalize(raw_name)
        if not norm:
            return None
        candidates = self.by_norm.get(norm)
        if not candidates:
            close = get_close_matches(norm, self.by_norm.keys(), n=1, cutoff=0.85)
            if close:
                candidates = self.by_norm[close[0]]
        if not candidates:
            return None
        if level:
            for z in candidates:
                if z.level == level:
                    return z
            return None
        for lvl in LEVEL_PRIORITY:
            for z in candidates:
                if z.level == lvl:
                    return z
        return candidates[0]


def zone_with_descendants_ids(db: Session, zone_id: int) -> list[int]:
    """Identifiants d'une zone et de toute sa descendance (agrégations)."""
    zones = db.query(AdminZone.id, AdminZone.parent_id).all()
    children: dict[int | None, list[int]] = {}
    for zid, parent in zones:
        children.setdefault(parent, []).append(zid)
    result: list[int] = []
    stack = [zone_id]
    while stack:
        current = stack.pop()
        result.append(current)
        stack.extend(children.get(current, []))
    return result
