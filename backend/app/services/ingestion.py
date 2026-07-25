"""Flux d'ingestion : prévisualisation → mapping → import.

L'import applique le garde-fou PII, résout les zones administratives et
produit un rapport détaillé (lignes acceptées / rejetées avec motifs).
"""
from dataclasses import dataclass, field

import pandas as pd
from sqlalchemy.orm import Session

from app.models import ColumnMapping, DataSource, Incident, Indicator, Site, Stock
from app.ontology import ENTITIES, normalize_status
from app.services import pii_guard
from app.services.parsing import build_preview, parse_file
from app.services.zone_matcher import ZoneMatcher, normalize


class ImportError_(Exception):
    """Erreur de validation d'un mapping ou d'un import (message utilisateur)."""


# Suggestions de mapping : mots-clés (normalisés) → champ cible par entité
FIELD_KEYWORDS: dict[str, dict[str, list[str]]] = {
    "site": {
        "name": ["nom", "site", "nom site", "nom du site", "etablissement", "name"],
        "site_type": ["type", "type site", "type de site", "categorie"],
        "zone": ["commune", "departement", "region", "zone", "localite"],
        "lat": ["lat", "latitude", "y"],
        "lon": ["lon", "lng", "longitude", "x"],
        "status": ["etat", "statut", "fonctionnel", "etat fonctionnel", "status"],
        "capacity": ["capacite", "capacity", "places"],
        "capacity_unit": ["unite capacite", "unite"],
    },
    "stock": {
        "resource_name": ["ressource", "produit", "article", "denree", "vivre"],
        "category": ["categorie", "famille", "type"],
        "quantity": ["quantite", "qte", "stock", "volume", "tonnage"],
        "unit": ["unite", "unit"],
        "site": ["site", "nom site", "entrepot", "magasin", "point de vente"],
        "zone": ["commune", "departement", "region", "zone"],
        "period_start": ["date", "debut", "periode", "mois"],
        "period_end": ["fin", "date fin"],
    },
    "incident": {
        "zone": ["commune", "departement", "region", "zone"],
        "incident_type": ["type", "type incident", "categorie", "nature"],
        "count": ["nombre", "nb", "count", "frequence", "occurrences", "cas"],
        "severity": ["severite", "gravite", "niveau"],
        "period_start": ["date", "debut", "periode", "mois"],
        "period_end": ["fin", "date fin"],
    },
    "indicator": {
        "name": ["indicateur", "nom", "nom indicateur", "variable"],
        "value": ["valeur", "value", "montant", "total", "nombre"],
        "unit": ["unite", "unit"],
        "zone": ["commune", "departement", "region", "zone"],
        "site": ["site", "nom site"],
        "period_start": ["date", "debut", "periode", "mois"],
        "period_end": ["fin", "date fin"],
    },
}


def suggest_fields(entity: str, columns: list[str]) -> dict[str, str]:
    """Suggère {colonne source → champ cible} par mots-clés normalisés."""
    keywords = FIELD_KEYWORDS.get(entity, {})
    suggestions: dict[str, str] = {}
    used_fields: set[str] = set()
    for col in columns:
        norm = normalize(col)
        best: str | None = None
        for fld, words in keywords.items():
            if fld in used_fields:
                continue
            if norm in words or any(w == norm or w in norm.split() for w in words):
                best = fld
                break
        if best:
            suggestions[col] = best
            used_fields.add(best)
    return suggestions


@dataclass
class ImportReport:
    accepted: int = 0
    rejected: int = 0
    warnings: list[str] = field(default_factory=list)
    rejects: list[dict] = field(default_factory=list)  # {row, reason}

    def reject(self, row_index: int, reason: str) -> None:
        self.rejected += 1
        if len(self.rejects) < 50:
            self.rejects.append({"row": row_index + 1, "reason": reason})

    def to_dict(self) -> dict:
        return {
            "accepted": self.accepted,
            "rejected": self.rejected,
            "warnings": self.warnings[:50],
            "rejects": self.rejects,
        }


def _convert(value, field_type: str):
    if value is None:
        return None
    text = str(value).strip()
    if text == "" or text.lower() in ("nan", "none", "null"):
        return None
    if field_type == "float":
        return float(text.replace(" ", "").replace(",", "."))
    if field_type == "int":
        return int(float(text.replace(" ", "").replace(",", ".")))
    if field_type == "date":
        ts = pd.to_datetime(text, dayfirst=True, format="mixed", errors="coerce")
        if pd.isna(ts):
            raise ValueError(f"date invalide : {text}")
        return ts.date()
    return text


def validate_mapping(
    entity: str,
    mappings: dict[str, str],
    defaults: dict[str, str],
    blocked_columns: set[str],
) -> None:
    """Vérifie le mapping avant import. Lève ImportError_ en français."""
    if entity not in ENTITIES:
        raise ImportError_(f"Objet métier inconnu : {entity}")
    fields = ENTITIES[entity]["fields"]
    for col, fld in mappings.items():
        if fld not in fields:
            raise ImportError_(
                f"Champ « {fld} » inconnu pour l'objet {ENTITIES[entity]['label']}."
            )
        if col in blocked_columns:
            raise ImportError_(
                f"La colonne « {col} » est bloquée par le garde-fou de données "
                "personnelles et ne peut pas être importée. Utilisez un agrégat "
                "par zone à la place."
            )
    provided = set(mappings.values()) | set(defaults.keys())
    missing = [
        f for f, spec in fields.items() if spec["required"] and f not in provided
    ]
    if entity == "stock" and "zone" not in provided and "site" not in provided:
        missing.append("zone")
    if missing:
        labels = ", ".join(f"« {fields[f]['label']} »" for f in dict.fromkeys(missing))
        raise ImportError_(f"Champs obligatoires non mappés : {labels}.")


def run_import(
    db: Session,
    source: DataSource,
    entity: str,
    mappings: dict[str, str],
    defaults: dict[str, str] | None = None,
    include_extra: bool = True,
) -> ImportReport:
    """Exécute l'import d'une source déjà prévisualisée."""
    defaults = defaults or {}
    content = open(source.stored_path, "rb").read()
    df = parse_file(source.filename, content)

    pii_report = pii_guard.scan_dataframe(
        list(df.columns), df.head(200).to_dict(orient="records")
    )
    validate_mapping(entity, mappings, defaults, pii_report.blocked_columns)

    fields = ENTITIES[entity]["fields"]
    matcher = ZoneMatcher(db)
    report = ImportReport()

    extra_columns = [
        c for c in df.columns
        if c not in mappings and c not in pii_report.blocked_columns
    ]
    for col in pii_report.blocked_columns:
        report.warnings.append(
            f"Colonne « {col} » exclue de l'import (garde-fou données personnelles)."
        )

    sites_cache = {
        (s.zone_id, normalize(s.name)): s for s in db.query(Site).all()
    }
    sites_by_name: dict[str, Site] = {}
    for s in sites_cache.values():
        sites_by_name.setdefault(normalize(s.name), s)

    for idx, row in df.iterrows():
        try:
            values: dict = {}
            for fld, spec in fields.items():
                raw = None
                for col, mapped_field in mappings.items():
                    if mapped_field == fld:
                        raw = row.get(col)
                if raw is None or (isinstance(raw, float) and pd.isna(raw)):
                    raw = defaults.get(fld)
                if raw is None or (isinstance(raw, float) and pd.isna(raw)):
                    values[fld] = None
                    continue
                if spec["type"] in ("zone", "site"):
                    values[fld] = str(raw).strip() or None
                else:
                    values[fld] = _convert(raw, spec["type"])

            missing = [
                f for f, spec in fields.items()
                if spec["required"] and values.get(f) is None
            ]
            if missing:
                report.reject(idx, f"valeur manquante : {', '.join(missing)}")
                continue

            zone = None
            if values.get("zone"):
                zone = matcher.match(values["zone"])
                if zone is None:
                    report.reject(idx, f"zone non reconnue : « {values['zone']} »")
                    continue

            linked_site = None
            if values.get("site"):
                site_norm = normalize(values["site"])
                if zone is not None:
                    linked_site = sites_cache.get((zone.id, site_norm))
                if linked_site is None:
                    linked_site = sites_by_name.get(site_norm)
                if linked_site is None and zone is None:
                    report.reject(idx, f"site inconnu : « {values['site']} »")
                    continue
                if linked_site is None:
                    report.warnings.append(
                        f"Ligne {idx + 1} : site « {values['site']} » inconnu, "
                        "rattachement à la zone seule."
                    )

            if entity in ("stock",) and zone is None and linked_site is not None:
                zone = linked_site.zone
            if entity != "site" and zone is None and linked_site is not None:
                zone = linked_site.zone
            if zone is None and entity != "site":
                report.reject(idx, "aucune zone résoluble")
                continue

            props = {}
            if include_extra:
                raw_props = {
                    c: (None if pd.isna(row[c]) else str(row[c]).strip())
                    for c in extra_columns
                }
                props = pii_guard.filter_properties(
                    {k: v for k, v in raw_props.items() if v}
                )

            obj = _build_object(
                entity, values, zone, linked_site, source.id, props or None
            )
            db.add(obj)
            if entity == "site":
                db.flush()
                key = (obj.zone_id, normalize(obj.name))
                sites_cache[key] = obj
                sites_by_name.setdefault(normalize(obj.name), obj)
            report.accepted += 1
        except (ValueError, TypeError) as exc:
            report.reject(idx, f"valeur invalide ({exc})")

    for col, fld in mappings.items():
        db.add(
            ColumnMapping(
                source_id=source.id,
                source_column=col,
                target_entity=entity,
                target_field=fld,
            )
        )
    source.status = "imported" if report.accepted else "failed"
    parse_report = dict(source.parse_report or {})
    parse_report["import"] = report.to_dict()
    parse_report["entity"] = entity
    source.parse_report = parse_report
    db.commit()
    return report


def _build_object(entity, values, zone, site, source_id, props):
    if entity == "site":
        return Site(
            name=values["name"],
            # types normalisés (minuscules, sans accents) pour un filtrage fiable
            site_type=normalize(values["site_type"]),
            zone_id=zone.id,
            lat=values.get("lat"),
            lon=values.get("lon"),
            status=normalize_status(values.get("status")),
            capacity=values.get("capacity"),
            capacity_unit=values.get("capacity_unit"),
            source_id=source_id,
            properties=props,
        )
    if entity == "stock":
        return Stock(
            site_id=site.id if site else None,
            zone_id=zone.id,
            resource_name=str(values["resource_name"]).strip(),
            category=values.get("category"),
            quantity=values["quantity"],
            unit=values.get("unit"),
            period_start=values.get("period_start"),
            period_end=values.get("period_end"),
            source_id=source_id,
            properties=props,
        )
    if entity == "incident":
        count = int(values["count"])
        if count < 1:
            raise ValueError("le nombre d'incidents doit être ≥ 1")
        return Incident(
            zone_id=zone.id,
            incident_type=normalize(values["incident_type"]),
            count=count,
            severity=values.get("severity"),
            period_start=values.get("period_start"),
            period_end=values.get("period_end"),
            source_id=source_id,
            properties=props,
        )
    if entity == "indicator":
        return Indicator(
            name=normalize(values["name"]),
            value=values["value"],
            unit=values.get("unit"),
            zone_id=zone.id,
            site_id=site.id if site else None,
            period_start=values.get("period_start"),
            period_end=values.get("period_end"),
            source_id=source_id,
            properties=props,
        )
    raise ImportError_(f"Objet métier inconnu : {entity}")


def preview_source(source: DataSource) -> dict:
    """(Re)construit la prévisualisation d'une source stockée."""
    content = open(source.stored_path, "rb").read()
    df = parse_file(source.filename, content)
    preview = build_preview(df)
    pii = pii_guard.scan_dataframe(
        [c["name"] for c in preview["columns"]],
        df.head(200).to_dict(orient="records"),
    )
    suggestions = {
        entity: suggest_fields(entity, [c["name"] for c in preview["columns"]])
        for entity in ENTITIES
    }
    return {
        "preview": preview,
        "pii_alerts": pii.to_dict(),
        "suggestions": suggestions,
    }
