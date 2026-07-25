"""Question en langage naturel → fonctions de requête → réponse en français.

Le LLM planifie (via des appels d'outils restreints), le backend exécute
(services/aggregation.py, SQL paramétré). Aucune génération de SQL libre :
seules des données agrégées peuvent être consultées.
"""
import json

from sqlalchemy.orm import Session

from app.models import AdminZone, RagQuery
from app.rag.provider import get_provider
from app.services import aggregation

TOOLS = [
    {
        "name": "count_sites",
        "description": "Compte les sites/infrastructures (centres de santé, écoles, "
        "points d'eau, sites de distribution, points de vente…) avec répartition par "
        "état, type et région. Filtres optionnels : type de site, état fonctionnel "
        "(fonctionnel/partiel/non_fonctionnel), zone (région, département ou commune).",
        "input_schema": {
            "type": "object",
            "properties": {
                "site_type": {"type": "string", "description": "Type de site (recherche partielle, ex : 'centre de sante')"},
                "status": {"type": "string", "description": "fonctionnel | partiel | non_fonctionnel | inconnu"},
                "zone": {"type": "string", "description": "Nom de zone administrative du Niger"},
            },
        },
    },
    {
        "name": "indicator_series",
        "description": "Série temporelle et total d'un indicateur agrégé "
        "(ex : beneficiaires_total, ventes_mensuelles, taux de rupture).",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Nom (partiel) de l'indicateur"},
                "zone": {"type": "string"},
                "period_start": {"type": "string", "description": "Date ISO AAAA-MM-JJ"},
                "period_end": {"type": "string", "description": "Date ISO AAAA-MM-JJ"},
            },
        },
    },
    {
        "name": "stock_summary",
        "description": "Totaux et évolution temporelle des stocks/ressources "
        "(vivres, kits, produits) par zone et période.",
        "input_schema": {
            "type": "object",
            "properties": {
                "resource": {"type": "string", "description": "Nom (partiel) de la ressource"},
                "zone": {"type": "string"},
                "period_start": {"type": "string"},
                "period_end": {"type": "string"},
            },
        },
    },
    {
        "name": "incidents_summary",
        "description": "Fréquence d'incidents AGRÉGÉS par zone : total, répartition "
        "par type et par région, série mensuelle. Aucune donnée individuelle.",
        "input_schema": {
            "type": "object",
            "properties": {
                "incident_type": {"type": "string"},
                "zone": {"type": "string"},
                "period_start": {"type": "string"},
                "period_end": {"type": "string"},
            },
        },
    },
]


def _execute(db: Session, name: str, args: dict) -> dict:
    if name == "count_sites":
        return aggregation.count_sites(
            db,
            site_type=args.get("site_type"),
            status=args.get("status"),
            zone=args.get("zone"),
        )
    if name == "indicator_series":
        return aggregation.indicator_series(
            db,
            name=args.get("name"),
            zone=args.get("zone"),
            period_start=args.get("period_start"),
            period_end=args.get("period_end"),
        )
    if name == "stock_summary":
        return aggregation.stock_summary(
            db,
            resource=args.get("resource"),
            zone=args.get("zone"),
            period_start=args.get("period_start"),
            period_end=args.get("period_end"),
        )
    if name == "incidents_summary":
        return aggregation.incidents_summary(
            db,
            incident_type=args.get("incident_type"),
            zone=args.get("zone"),
            period_start=args.get("period_start"),
            period_end=args.get("period_end"),
        )
    return {"error": f"Fonction inconnue : {name}"}


def _system_prompt(db: Session) -> str:
    catalog = aggregation.catalog(db)
    regions = [
        z.name for z in db.query(AdminZone).filter_by(level="region").all()
    ]
    return (
        "Tu es l'assistant d'une plateforme d'intégration de données pour le Niger. "
        "Tu réponds en français, de façon concise et chiffrée, uniquement à partir "
        "des résultats des outils fournis — jamais de tes connaissances générales. "
        "Les données sont exclusivement agrégées (sites, stocks, incidents par zone, "
        "indicateurs) ; il n'existe aucune donnée sur des personnes identifiables, "
        "et tu refuses poliment toute question qui en demanderait.\n"
        f"Régions du Niger : {', '.join(regions)}.\n"
        f"Types de sites en base : {catalog['site_types']}.\n"
        f"Indicateurs disponibles : {catalog['indicators']}.\n"
        f"Ressources en stock : {catalog['resources']}.\n"
        f"Types d'incidents : {catalog['incident_types']}.\n"
        "Si les données sont vides, dis-le clairement. Mentionne la zone et la "
        "période couvertes par ta réponse."
    )


def answer_question(db: Session, question: str) -> dict:
    provider = get_provider()
    system = _system_prompt(db)
    messages: list[dict] = [{"role": "user", "content": question}]
    plan: list[dict] = []

    for _ in range(5):
        response = provider.complete(system, messages, TOOLS)
        if not response.tool_calls:
            answer = response.text.strip() or "Je n'ai pas pu formuler de réponse."
            log = RagQuery(question=question, plan={"steps": plan}, answer=answer)
            db.add(log)
            db.commit()
            return {"answer": answer, "steps": plan}

        messages.append({"role": "assistant", "content": response.raw_content})
        results = []
        for call in response.tool_calls:
            result = _execute(db, call.name, call.input)
            plan.append({"function": call.name, "args": call.input, "result": result})
            results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": call.id,
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                }
            )
        messages.append({"role": "user", "content": results})

    answer = "La question a demandé trop d'étapes ; reformulez-la plus simplement."
    db.add(RagQuery(question=question, plan={"steps": plan}, answer=answer))
    db.commit()
    return {"answer": answer, "steps": plan}
