"""Registre de l'ontologie : les objets métier et leurs champs mappables.

Ce registre est la source de vérité pour :
- l'éditeur de mapping du frontend (GET /api/ontology) ;
- la validation et l'import (services/ingestion.py) ;
- la documentation du schéma transmise au LLM (rag/nl2query.py).

Contrainte structurelle : aucune entité de type « personne » ne peut être
ajoutée ici. Les seules entités admises représentent des infrastructures,
des ressources ou des agrégats par zone.
"""

# type: str | float | int | date | zone (nom de zone à résoudre) | site (nom de site à lier)
ENTITIES: dict = {
    "site": {
        "label": "Site / Infrastructure",
        "description": "Un lieu physique : centre de santé, école, point d'eau, "
        "site de distribution, point de vente, entrepôt…",
        "fields": {
            "name": {"label": "Nom du site", "type": "str", "required": True},
            "site_type": {"label": "Type de site", "type": "str", "required": True},
            "zone": {"label": "Zone administrative", "type": "zone", "required": True},
            "lat": {"label": "Latitude", "type": "float", "required": False},
            "lon": {"label": "Longitude", "type": "float", "required": False},
            "status": {
                "label": "État fonctionnel",
                "type": "str",
                "required": False,
                "help": "fonctionnel, partiel, non_fonctionnel, inconnu",
            },
            "capacity": {"label": "Capacité", "type": "float", "required": False},
            "capacity_unit": {
                "label": "Unité de capacité",
                "type": "str",
                "required": False,
            },
        },
    },
    "stock": {
        "label": "Ressource / Stock",
        "description": "Une quantité de ressource à une période, rattachée à un "
        "site et/ou une zone (vivres, kits, produits, carburant…).",
        "fields": {
            "resource_name": {"label": "Ressource", "type": "str", "required": True},
            "category": {"label": "Catégorie", "type": "str", "required": False},
            "quantity": {"label": "Quantité", "type": "float", "required": True},
            "unit": {"label": "Unité", "type": "str", "required": False},
            "site": {"label": "Site de rattachement", "type": "site", "required": False},
            "zone": {"label": "Zone administrative", "type": "zone", "required": False},
            "period_start": {"label": "Début de période", "type": "date", "required": False},
            "period_end": {"label": "Fin de période", "type": "date", "required": False},
        },
        "note": "Zone requise si aucun site n'est fourni (elle est sinon héritée du site).",
    },
    "incident": {
        "label": "Incident (agrégé par zone)",
        "description": "Un comptage d'incidents par zone, type et période. "
        "Jamais d'événement individuel ni de coordonnées.",
        "fields": {
            "zone": {"label": "Zone administrative", "type": "zone", "required": True},
            "incident_type": {"label": "Type d'incident", "type": "str", "required": True},
            "count": {"label": "Nombre d'incidents", "type": "int", "required": True},
            "severity": {"label": "Sévérité", "type": "str", "required": False},
            "period_start": {"label": "Début de période", "type": "date", "required": False},
            "period_end": {"label": "Fin de période", "type": "date", "required": False},
        },
    },
    "indicator": {
        "label": "Indicateur",
        "description": "Une valeur agrégée : nom + valeur + unité + période + zone "
        "(ex. bénéficiaires totaux, taux de fonctionnalité, ventes mensuelles).",
        "fields": {
            "name": {"label": "Nom de l'indicateur", "type": "str", "required": True},
            "value": {"label": "Valeur", "type": "float", "required": True},
            "unit": {"label": "Unité", "type": "str", "required": False},
            "zone": {"label": "Zone administrative", "type": "zone", "required": True},
            "site": {"label": "Site de rattachement", "type": "site", "required": False},
            "period_start": {"label": "Début de période", "type": "date", "required": False},
            "period_end": {"label": "Fin de période", "type": "date", "required": False},
        },
    },
}

# Normalisation des états fonctionnels rencontrés dans les fichiers
STATUS_ALIASES = {
    "fonctionnel": "fonctionnel",
    "fonctionnelle": "fonctionnel",
    "oui": "fonctionnel",
    "ok": "fonctionnel",
    "actif": "fonctionnel",
    "operationnel": "fonctionnel",
    "opérationnel": "fonctionnel",
    "partiel": "partiel",
    "partiellement fonctionnel": "partiel",
    "degrade": "partiel",
    "dégradé": "partiel",
    "non fonctionnel": "non_fonctionnel",
    "non_fonctionnel": "non_fonctionnel",
    "non": "non_fonctionnel",
    "ferme": "non_fonctionnel",
    "fermé": "non_fonctionnel",
    "hors service": "non_fonctionnel",
    "en panne": "non_fonctionnel",
}


def normalize_status(raw: str | None) -> str:
    if not raw:
        return "inconnu"
    return STATUS_ALIASES.get(str(raw).strip().lower(), str(raw).strip().lower())
