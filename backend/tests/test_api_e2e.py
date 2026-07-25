"""Tests de bout en bout : upload → mapping → import → carte/dashboard/RAG."""
import io

CSV_SITES = """nom_site;type;commune;etat;capacite;latitude;longitude
CSI Ouallam;centre de sante;Ouallam;fonctionnel;120;14.32;2.09
CSI Téra;centre de sante;Téra;non fonctionnel;80;14.01;0.75
Ecole Diffa 1;ecole;Diffa;fonctionnel;350;13.32;12.61
Forage Dakoro;point d'eau;Dakoro;partiel;;14.51;6.77
Site inconnu;ecole;Atlantide;fonctionnel;10;;
"""

CSV_PII = """nom_beneficiaire;telephone;commune;quantite
Amadou X;+227 96 00 00 01;Ouallam;10
"""

CSV_INCIDENTS = """region;type_incident;nombre;date
Tillabéri;incident d'acces;4;01/03/2025
Diffa;incident d'acces;2;01/03/2025
Tillabéri;vol;1;15/03/2025
"""


def _upload(client, name, content):
    return client.post(
        "/api/uploads",
        files={"file": (name, io.BytesIO(content.encode()), "text/csv")},
        data={"uploaded_by": "test", "domain": "test"},
    )


class TestZones:
    def test_arbre_zones(self, client):
        tree = client.get("/api/zones").json()
        names = {r["name"] for r in tree}
        assert names == {"Agadez", "Diffa", "Dosso", "Maradi", "Niamey",
                         "Tahoua", "Tillabéri", "Zinder"}
        tillaberi = next(r for r in tree if r["name"] == "Tillabéri")
        assert len(tillaberi["children"]) == 13

    def test_geojson_regions(self, client):
        geo = client.get("/api/zones/geojson?level=region").json()
        assert len(geo["features"]) == 8


class TestIngestion:
    def test_flux_complet_sites(self, client):
        r = _upload(client, "sites.csv", CSV_SITES)
        assert r.status_code == 200, r.text
        body = r.json()
        source_id = body["source"]["id"]
        assert body["preview"]["row_count"] == 5
        assert body["pii_alerts"] == []
        # suggestions automatiques de mapping
        assert body["suggestions"]["site"].get("nom_site") == "name"

        r = client.post(
            f"/api/uploads/{source_id}/import",
            json={
                "entity": "site",
                "mappings": {
                    "nom_site": "name", "type": "site_type", "commune": "zone",
                    "etat": "status", "capacite": "capacity",
                    "latitude": "lat", "longitude": "lon",
                },
            },
        )
        assert r.status_code == 200, r.text
        report = r.json()["report"]
        assert report["accepted"] == 4
        assert report["rejected"] == 1  # zone « Atlantide » inconnue
        assert "Atlantide" in report["rejects"][0]["reason"]

        sites = client.get("/api/sites", params={"zone": "Tillabéri"}).json()
        assert {s["name"] for s in sites} == {"CSI Ouallam", "CSI Téra"}
        assert sites[0]["status"] in ("fonctionnel", "non_fonctionnel")

    def test_pii_bloque(self, client):
        r = _upload(client, "pii.csv", CSV_PII)
        body = r.json()
        blocked = {a["column"] for a in body["pii_alerts"]}
        assert "nom_beneficiaire" in blocked and "telephone" in blocked
        # le mapping d'une colonne bloquée est refusé
        r = client.post(
            f"/api/uploads/{body['source']['id']}/import",
            json={"entity": "indicator",
                  "mappings": {"nom_beneficiaire": "name", "quantite": "value",
                               "commune": "zone"}},
        )
        assert r.status_code == 400
        assert "garde-fou" in r.json()["detail"]

    def test_incidents_agreges(self, client):
        r = _upload(client, "incidents.csv", CSV_INCIDENTS)
        source_id = r.json()["source"]["id"]
        r = client.post(
            f"/api/uploads/{source_id}/import",
            json={"entity": "incident",
                  "mappings": {"region": "zone", "type_incident": "incident_type",
                               "nombre": "count", "date": "period_start"}},
        )
        assert r.json()["report"]["accepted"] == 3

        summary = client.get("/api/dashboard/summary",
                             params={"zone": "Tillabéri"}).json()
        assert summary["incidents"]["total"] == 5  # 4 + 1

    def test_import_deux_fois_refuse(self, client):
        r = _upload(client, "sites2.csv", "nom;type;commune\nA;ecole;Dosso\n")
        sid = r.json()["source"]["id"]
        payload = {"entity": "site",
                   "mappings": {"nom": "name", "type": "site_type", "commune": "zone"}}
        assert client.post(f"/api/uploads/{sid}/import", json=payload).status_code == 200
        assert client.post(f"/api/uploads/{sid}/import", json=payload).status_code == 409


class TestDashboardEtRag:
    def test_carte_incidents(self, client):
        stats = client.get("/api/dashboard/map", params={"metric": "incidents"}).json()
        assert stats["by_region"].get("Tillabéri") == 5

    def test_question_sites(self, client):
        r = client.post("/api/ask",
                        json={"question": "Combien de centres de santé fonctionnels à Ouallam ?"})
        assert r.status_code == 200
        body = r.json()
        assert body["steps"][0]["function"] == "count_sites"
        assert "1" in body["answer"]

    def test_question_incidents(self, client):
        r = client.post("/api/ask",
                        json={"question": "Combien d'incidents à Tillabéri ?"})
        body = r.json()
        assert body["steps"][0]["function"] == "incidents_summary"
        assert "5" in body["answer"]

    def test_historique(self, client):
        history = client.get("/api/ask/history").json()
        assert len(history) >= 2
