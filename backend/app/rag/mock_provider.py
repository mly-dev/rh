"""Fournisseur simulé : permet de développer et démontrer le RAG sans clé API.

Premier tour : devine la fonction de requête par mots-clés (et la zone par
recherche des noms de zones du Niger dans la question). Deuxième tour :
formule une réponse en français à partir du résultat d'outil.
"""
import json
import uuid

from app.rag.provider import LLMProvider, LLMResponse, ToolCall
from app.services.zone_matcher import normalize

REGIONS = [
    "Agadez", "Diffa", "Dosso", "Maradi", "Niamey", "Tahoua", "Tillabéri", "Zinder",
]
COMMON_ZONES = REGIONS + [
    "Ouallam", "Téra", "Say", "Kollo", "Filingué", "Abala", "Dakoro", "Tessaoua",
    "Madarounfa", "N'Guigmi", "Maïné-Soroa", "Gaya", "Dogondoutchi", "Birni N'Konni",
    "Madaoua", "Magaria", "Mirriah", "Tanout", "Arlit", "Torodi", "Banibangou",
]

SITE_KEYWORDS = {
    "centre de sante": ["centre de sante", "centres de sante", "sante"],
    "ecole": ["ecole", "ecoles", "scolaire"],
    "point d'eau": ["point d eau", "points d eau", "forage", "puits"],
    "site de distribution": ["distribution"],
    "point de vente": ["point de vente", "points de vente", "boutique", "magasin"],
}


class MockProvider(LLMProvider):
    def complete(
        self, system: str, messages: list[dict], tools: list[dict]
    ) -> LLMResponse:
        last = messages[-1]
        if isinstance(last.get("content"), list):  # résultat d'outil → réponse
            return self._answer(last["content"])
        return self._plan(str(last.get("content", "")))

    def _plan(self, question: str) -> LLMResponse:
        q = normalize(question)
        zone = next(
            (z for z in COMMON_ZONES if normalize(z) in q.split() or normalize(z) in q),
            None,
        )
        args: dict = {}
        if zone:
            args["zone"] = zone

        if "incident" in q or "securite" in q or "attaque" in q:
            name = "incidents_summary"
        elif "stock" in q or "vivre" in q or "riz" in q or "carburant" in q:
            name = "stock_summary"
        elif any(w in q for w in ("beneficiaire", "indicateur", "vente", "taux", "rupture")):
            name = "indicator_series"
            for key in ("beneficiaire", "vente", "rupture"):
                if key in q:
                    args["name"] = key
        else:
            name = "count_sites"
            for site_type, words in SITE_KEYWORDS.items():
                if any(w in q for w in words):
                    args["site_type"] = site_type
                    break
            if "fonctionnel" in q and "non fonctionnel" not in q:
                args["status"] = "fonctionnel"
            elif "non fonctionnel" in q or "panne" in q or "ferme" in q:
                args["status"] = "non_fonctionnel"

        call = ToolCall(id=f"mock_{uuid.uuid4().hex[:8]}", name=name, input=args)
        raw = [
            {"type": "text", "text": ""},
            {"type": "tool_use", "id": call.id, "name": call.name, "input": call.input},
        ]
        return LLMResponse(tool_calls=[call], raw_content=raw)

    def _answer(self, tool_results: list[dict]) -> LLMResponse:
        try:
            data = json.loads(tool_results[0]["content"])
        except (KeyError, ValueError, IndexError):
            return LLMResponse(text="Je n'ai pas pu interpréter les résultats.")
        if "error" in data:
            return LLMResponse(text=f"Impossible de répondre : {data['error']}")

        zone = data.get("zone", "Niger")
        parts: list[str] = []
        if "by_status" in data:  # count_sites
            parts.append(f"On dénombre {data['total']} site(s) pour {zone}.")
            if data.get("by_status"):
                détail = ", ".join(f"{v} {k}" for k, v in data["by_status"].items())
                parts.append(f"Par état : {détail}.")
            if data.get("by_type") and len(data["by_type"]) > 1:
                détail = ", ".join(f"{v} {k}" for k, v in data["by_type"].items())
                parts.append(f"Par type : {détail}.")
        elif "by_resource" in data:  # stock_summary
            if not data.get("by_resource"):
                parts.append(f"Aucun stock enregistré pour {zone}.")
            else:
                parts.append(f"Stocks pour {zone} :")
                for res, info in data["by_resource"].items():
                    unit = info.get("unit") or ""
                    parts.append(f"- {res} : {info['quantity']} {unit}".rstrip())
                if data.get("series") and len(data["series"]) > 1:
                    first, dernier = data["series"][0], data["series"][-1]
                    parts.append(
                        f"Évolution : {first['quantity']} ({first['period']}) → "
                        f"{dernier['quantity']} ({dernier['period']})."
                    )
        elif "by_type" in data:  # incidents_summary
            total = data.get("total", 0)
            if not total:
                parts.append(f"Aucun incident enregistré pour {zone}.")
            else:
                parts.append(f"{total} incident(s) agrégé(s) pour {zone}.")
                détail = ", ".join(f"{v} {k}" for k, v in data["by_type"].items())
                parts.append(f"Par type : {détail}.")
        elif "series" in data:  # indicator_series
            if not data["series"]:
                parts.append(f"Aucune donnée pour l'indicateur demandé ({zone}).")
            else:
                unit = data.get("unit") or ""
                parts.append(
                    f"Indicateur « {data.get('indicator')} » pour {zone} : "
                    f"total {data['total']} {unit}".rstrip() + "."
                )
                if len(data["series"]) > 1:
                    first, dernier = data["series"][0], data["series"][-1]
                    parts.append(
                        f"Évolution : {first['value']} ({first['period']}) → "
                        f"{dernier['value']} ({dernier['period']})."
                    )
        else:
            parts.append(json.dumps(data, ensure_ascii=False))
        parts.append("(Réponse générée par le mode démonstration, sans LLM.)")
        return LLMResponse(text=" ".join(parts))
