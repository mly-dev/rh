"""Génération des trois jeux de données de démonstration (données fictives
réalistes, vraies zones du Niger) et injection via le pipeline d'ingestion
standard de l'API — ce qui teste le pipeline lui-même.

Usage :
    python scripts/demo_data.py [--api http://localhost:8000] [--only humanitaire|gouvernemental|commercial]

Les CSV générés sont écrits dans scripts/output/ puis téléversés, mappés et
importés via /api/uploads. Aucune donnée personnelle : uniquement des sites,
stocks, incidents agrégés par zone et indicateurs.
"""
import argparse
import csv
import random
import sys
from pathlib import Path

import httpx

OUT = Path(__file__).parent / "output"
MONTHS = ["01/01/2025", "01/02/2025", "01/03/2025", "01/04/2025", "01/05/2025", "01/06/2025"]

COMMUNES_HUM = [
    ("Diffa", "Diffa"), ("N'Guigmi", "Diffa"), ("Maïné-Soroa", "Diffa"),
    ("Bosso", "Diffa"), ("Ouallam", "Tillabéri"), ("Téra", "Tillabéri"),
    ("Abala", "Tillabéri"), ("Banibangou", "Tillabéri"), ("Ayérou", "Tillabéri"),
    ("Dakoro", "Maradi"), ("Guidan Roumdji", "Maradi"), ("Madarounfa", "Maradi"),
]
COMMUNE_COORDS = {
    "Diffa": (13.32, 12.61), "N'Guigmi": (14.25, 13.11), "Maïné-Soroa": (13.21, 11.98),
    "Bosso": (13.70, 13.30), "Ouallam": (14.32, 2.09), "Téra": (14.01, 0.75),
    "Abala": (14.93, 3.43), "Banibangou": (15.03, 2.70), "Ayérou": (14.73, 0.92),
    "Dakoro": (14.51, 6.77), "Guidan Roumdji": (13.66, 6.70), "Madarounfa": (13.31, 7.16),
    "Agadez": (16.97, 7.99), "Arlit": (18.74, 7.39), "Dosso": (13.05, 3.19),
    "Gaya": (11.89, 3.45), "Dogondoutchi": (13.64, 4.03), "Birni N'Konni": (13.80, 5.25),
    "Tahoua": (14.89, 5.26), "Madaoua": (14.08, 5.96), "Maradi": (13.50, 7.10),
    "Tessaoua": (13.75, 7.99), "Zinder": (13.80, 8.99), "Magaria": (12.99, 8.91),
    "Mirriah": (13.71, 9.15), "Tanout": (14.97, 8.89), "Niamey": (13.51, 2.11),
    "Tillabéri": (14.21, 1.45), "Kollo": (13.30, 2.34), "Say": (13.10, 2.36),
    "Filingué": (14.35, 3.32), "Gouré": (13.98, 10.27), "Mayahi": (13.96, 7.67),
    "Illéla": (14.46, 5.24), "Kéita": (14.75, 5.77), "Loga": (13.61, 3.23),
}
ALL_COMMUNES = list(COMMUNE_COORDS)


def _write_csv(name: str, header: list[str], rows: list[list]) -> Path:
    OUT.mkdir(exist_ok=True)
    path = OUT / name
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(header)
        writer.writerows(rows)
    return path


def _jitter(base: tuple[float, float]) -> tuple[float, float]:
    return (round(base[0] + random.uniform(-0.05, 0.05), 4),
            round(base[1] + random.uniform(-0.05, 0.05), 4))


# ---------------------------------------------------------------- humanitaire
def gen_humanitaire() -> list[tuple[Path, str, dict, dict]]:
    """Sites de distribution, stocks de vivres, bénéficiaires agrégés,
    incidents d'accès. Retourne [(fichier, entité, mappings, defaults)]."""
    random.seed(42)
    files = []

    sites = []
    for commune, _region in COMMUNES_HUM:
        for i in range(random.randint(1, 2)):
            lat, lon = _jitter(COMMUNE_COORDS[commune])
            sites.append([
                f"Site de distribution {commune} {i + 1}", "site de distribution",
                commune, random.choice(["fonctionnel"] * 4 + ["partiel"]),
                random.choice([500, 800, 1000, 1500]), lat, lon,
            ])
    files.append((
        _write_csv("hum_sites_distribution.csv",
                   ["nom_site", "type_site", "commune", "etat", "capacite_menages", "latitude", "longitude"],
                   sites),
        "site",
        {"nom_site": "name", "type_site": "site_type", "commune": "zone",
         "etat": "status", "capacite_menages": "capacity", "latitude": "lat",
         "longitude": "lon"},
        {"capacity_unit": "ménages"},
    ))

    stocks = []
    for commune, _region in COMMUNES_HUM:
        site = f"Site de distribution {commune} 1"
        for produit, unite, base in [("riz", "tonnes", 40), ("mil", "tonnes", 30),
                                     ("huile", "litres", 2000)]:
            level = base * random.uniform(0.8, 1.3)
            for month in MONTHS:
                level = max(0, level * random.uniform(0.75, 1.15))
                stocks.append([produit, "vivres", round(level, 1), unite, site, commune, month])
    files.append((
        _write_csv("hum_stocks_vivres.csv",
                   ["ressource", "categorie", "quantite", "unite", "site", "commune", "mois"],
                   stocks),
        "stock",
        {"ressource": "resource_name", "categorie": "category", "quantite": "quantity",
         "unite": "unit", "site": "site", "commune": "zone", "mois": "period_start"},
        {},
    ))

    benef = []
    for commune, _region in COMMUNES_HUM:
        base = random.randint(800, 4000)
        for month in MONTHS:
            base = int(base * random.uniform(0.9, 1.2))
            benef.append(["beneficiaires_total", base, "personnes", commune, month])
    files.append((
        _write_csv("hum_beneficiaires_agreges.csv",
                   ["indicateur", "valeur", "unite", "commune", "mois"], benef),
        "indicator",
        {"indicateur": "name", "valeur": "value", "unite": "unit",
         "commune": "zone", "mois": "period_start"},
        {},
    ))

    incidents = []
    for dept in ["Ouallam", "Téra", "Banibangou", "Abala", "Diffa", "N'Guigmi",
                 "Bosso", "Dakoro"]:
        for month in MONTHS:
            if random.random() < 0.7:
                incidents.append([
                    dept, "incident d'accès",
                    random.randint(1, 6),
                    random.choice(["faible", "moyenne", "élevée"]), month,
                ])
    files.append((
        _write_csv("hum_incidents_acces.csv",
                   ["departement", "type_incident", "nombre", "severite", "mois"],
                   incidents),
        "incident",
        {"departement": "zone", "type_incident": "incident_type", "nombre": "count",
         "severite": "severity", "mois": "period_start"},
        {},
    ))
    return files


# -------------------------------------------------------------- gouvernemental
def gen_gouvernemental() -> list[tuple[Path, str, dict, dict]]:
    """Infrastructures publiques : écoles, centres de santé, points d'eau."""
    random.seed(43)
    rows = []
    types = [
        ("école primaire", "élèves", (100, 600)),
        ("centre de santé", "consultations/mois", (200, 1500)),
        ("point d'eau", "personnes desservies", (300, 2500)),
    ]
    for commune in ALL_COMMUNES:
        for type_site, unite, (lo, hi) in types:
            for i in range(random.randint(1, 3)):
                lat, lon = _jitter(COMMUNE_COORDS[commune])
                rows.append([
                    f"{type_site.capitalize()} {commune} {i + 1}", type_site, commune,
                    random.choice(["fonctionnel"] * 6 + ["partiel"] * 2 + ["non fonctionnel"]),
                    random.randint(lo, hi), unite, lat, lon,
                ])
    path = _write_csv("gouv_infrastructures.csv",
                      ["nom", "type", "commune", "etat_fonctionnel", "capacite",
                       "unite_capacite", "latitude", "longitude"], rows)
    return [(
        path, "site",
        {"nom": "name", "type": "site_type", "commune": "zone",
         "etat_fonctionnel": "status", "capacite": "capacity",
         "unite_capacite": "capacity_unit", "latitude": "lat", "longitude": "lon"},
        {},
    )]


# ------------------------------------------------------------------ commercial
def gen_commercial() -> list[tuple[Path, str, dict, dict]]:
    """Réseau de points de vente : ventes mensuelles, taux de rupture."""
    random.seed(44)
    files = []
    villes = ["Niamey", "Maradi", "Zinder", "Tahoua", "Agadez", "Dosso",
              "Diffa", "Tillabéri", "Birni N'Konni", "Arlit", "Gaya", "Tessaoua"]

    sites = []
    for ville in villes:
        for i in range(random.randint(1, 3)):
            lat, lon = _jitter(COMMUNE_COORDS[ville])
            sites.append([f"Point de vente {ville} {i + 1}", "point de vente", ville,
                          "fonctionnel", lat, lon])
    files.append((
        _write_csv("com_points_vente.csv",
                   ["nom", "type", "ville", "etat", "latitude", "longitude"], sites),
        "site",
        {"nom": "name", "type": "site_type", "ville": "zone", "etat": "status",
         "latitude": "lat", "longitude": "lon"},
        {},
    ))

    ventes = []
    ruptures = []
    for ville in villes:
        base = random.randint(2, 15) * 1_000_000
        for month in MONTHS:
            base = int(base * random.uniform(0.85, 1.25))
            ventes.append(["ventes_mensuelles", base, "FCFA", ville, month])
            ruptures.append(["taux_rupture", round(random.uniform(2, 18), 1), "%", ville, month])
    files.append((
        _write_csv("com_ventes.csv",
                   ["indicateur", "valeur", "unite", "ville", "mois"], ventes),
        "indicator",
        {"indicateur": "name", "valeur": "value", "unite": "unit", "ville": "zone",
         "mois": "period_start"},
        {},
    ))
    files.append((
        _write_csv("com_ruptures.csv",
                   ["indicateur", "valeur", "unite", "ville", "mois"], ruptures),
        "indicator",
        {"indicateur": "name", "valeur": "value", "unite": "unit", "ville": "zone",
         "mois": "period_start"},
        {},
    ))

    stocks = []
    for ville in villes[:6]:
        site = f"Point de vente {ville} 1"
        for produit in ["farine", "sucre", "savon"]:
            level = random.randint(200, 900)
            for month in MONTHS:
                level = max(0, int(level * random.uniform(0.7, 1.3)))
                stocks.append([produit, "produits", level, "unités", site, ville, month])
    files.append((
        _write_csv("com_stocks.csv",
                   ["produit", "categorie", "quantite", "unite", "magasin", "ville", "mois"],
                   stocks),
        "stock",
        {"produit": "resource_name", "categorie": "category", "quantite": "quantity",
         "unite": "unit", "magasin": "site", "ville": "zone", "mois": "period_start"},
        {},
    ))
    return files


DOMAINS = {
    "humanitaire": gen_humanitaire,
    "gouvernemental": gen_gouvernemental,
    "commercial": gen_commercial,
}


def inject(api: str, domain: str, batch) -> None:
    with httpx.Client(base_url=api, timeout=120) as client:
        for path, entity, mappings, defaults in batch:
            with open(path, "rb") as f:
                r = client.post(
                    "/api/uploads",
                    files={"file": (path.name, f, "text/csv")},
                    data={"uploaded_by": "générateur de démo", "domain": domain},
                )
            r.raise_for_status()
            source = r.json()["source"]
            r = client.post(
                f"/api/uploads/{source['id']}/import",
                json={"entity": entity, "mappings": mappings, "defaults": defaults},
            )
            r.raise_for_status()
            report = r.json()["report"]
            status = "OK" if not report["rejected"] else "ATTENTION"
            print(f"  [{status}] {path.name} → {entity} : "
                  f"{report['accepted']} acceptées, {report['rejected']} rejetées")
            for reject in report["rejects"][:5]:
                print(f"        ligne {reject['row']} : {reject['reason']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--only", choices=list(DOMAINS))
    parser.add_argument("--no-inject", action="store_true",
                        help="générer les CSV sans les importer")
    args = parser.parse_args()

    for domain, generator in DOMAINS.items():
        if args.only and domain != args.only:
            continue
        print(f"— Jeu {domain}")
        batch = generator()
        if args.no_inject:
            for path, *_ in batch:
                print(f"  généré : {path}")
        else:
            try:
                inject(args.api, domain, batch)
            except httpx.ConnectError:
                print(f"  ERREUR : API injoignable sur {args.api} — démarrez le backend.")
                sys.exit(1)


if __name__ == "__main__":
    main()
