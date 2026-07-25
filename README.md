# Plateforme d'intégration de données — Niger

Plateforme d'intégration et d'analyse de données inspirée de Palantir Foundry,
adaptée au Niger et à l'Afrique de l'Ouest. Un même noyau technique sert trois
audiences : **ONG/humanitaire**, **administrations publiques** et **PME**
(business intelligence), avec trois jeux de données de démonstration.

> **Périmètre strict :** la plateforme traite uniquement des données
> **agrégées et d'infrastructures** (sites, stocks, incidents par zone,
> indicateurs). Le modèle de données ne permet pas de stocker ni de relier des
> personnes identifiables — c'est une contrainte de conception (voir
> [ARCHITECTURE.md](ARCHITECTURE.md), section « Garde-fous anti-PII »).

## Fonctionnalités

- **Ingestion** : upload CSV / Excel / PDF (tableaux), détection des colonnes
  et types, prévisualisation, garde-fou anti-données-personnelles, traçabilité
  complète des sources.
- **Ontologie légère** : mapping des colonnes vers 4 objets métier — `Site`,
  `Stock`, `Incident` (agrégé par zone), `Indicateur` — chacun rattaché aux
  vraies zones administratives du Niger (8 régions → départements → communes).
- **Carte & dashboards** : choroplèthe par région (Leaflet), markers de sites
  par état fonctionnel, graphiques auto-générés (Recharts), filtres.
- **RAG** : questions en français (« Combien de centres de santé fonctionnels
  à Tillabéri ? ») traduites en fonctions de requête restreintes — jamais de
  SQL généré par le LLM. Fonctionne sans clé API (mode démonstration) ou avec
  l'API Anthropic.

## Démarrage rapide (développement local)

Prérequis : Python 3.11+, Node 18+, PostgreSQL (ou Docker, voir plus bas).

```bash
# 1. Base de données
sudo -u postgres psql -c "CREATE USER niger WITH PASSWORD 'niger' CREATEDB;" \
                       -c "CREATE DATABASE niger_data OWNER niger;"

# 2. Backend (http://localhost:8000, docs sur /docs)
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload          # crée les tables + seed des zones au démarrage

# 3. Données de démonstration (3 jeux fictifs réalistes, via le pipeline d'ingestion)
python ../scripts/demo_data.py

# 4. Frontend (http://localhost:5173)
cd ../frontend
npm install
npm run dev
```

### Avec Docker

```bash
docker compose up --build
# puis : python scripts/demo_data.py
```

### Tests

```bash
cd backend && python -m pytest tests/   # 27 tests (unitaires + bout en bout)
```

## Activer le LLM (Anthropic)

Sans configuration, le RAG tourne en **mode démonstration** (heuristiques,
aucune clé requise). Pour brancher l'API Anthropic :

```bash
export LLM_PROVIDER=anthropic
export ANTHROPIC_API_KEY=sk-ant-...
# optionnel : export ANTHROPIC_MODEL=claude-opus-5
```

L'abstraction est dans `backend/app/rag/provider.py` ; le LLM ne dispose que
de 4 fonctions de requête agrégées (`count_sites`, `indicator_series`,
`stock_summary`, `incidents_summary`) exécutées par le backend en SQL
paramétré.

## Structure du projet

```
backend/    FastAPI + SQLAlchemy (PostgreSQL) — ingestion, ontologie, agrégations, RAG
frontend/   React + Vite + Tailwind — carte Leaflet, dashboards Recharts, 5 pages
scripts/    demo_data.py — génération + injection des 3 jeux de démonstration
ARCHITECTURE.md  — architecture, schéma de données, garde-fous anti-PII
```

## Jeux de démonstration

| Domaine | Contenu |
|---|---|
| Humanitaire | Sites de distribution (Diffa, Tillabéri, Maradi), stocks de vivres mensuels, bénéficiaires **en nombre agrégé par commune**, incidents d'accès par département |
| Gouvernemental | Écoles, centres de santé, points d'eau : localisation, état fonctionnel, capacité (8 régions) |
| Commercial | Points de vente, ventes mensuelles (FCFA), stocks et taux de rupture par ville |

## Limites connues du MVP

- Frontières régionales **simplifiées et indicatives** (les sources
  officielles COD-AB/OCHA n'étaient pas accessibles depuis l'environnement de
  développement) — remplacer `backend/app/data/geo/regions.geojson`.
- Pas d'authentification (le champ « téléversé par » est déclaratif).
- PostGIS optionnel : le MVP n'utilise pas de colonne géométrique (GeoJSON
  statique + centroïdes), l'image Docker PostGIS est prête pour la suite.
