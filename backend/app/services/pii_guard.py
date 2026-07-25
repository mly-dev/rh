"""Garde-fou anti-données personnelles (contrainte de conception).

La plateforme ne traite que des données agrégées et d'infrastructures.
Ce module bloque, dès la prévisualisation et avant tout import :
- les colonnes dont le nom désigne une personne identifiable
  (prénom, téléphone, identifiant national, date de naissance…) ;
- les colonnes dont le contenu ressemble à des téléphones ou emails ;
- les clés interdites dans les propriétés additionnelles (JSONB).

Chaque blocage produit un message en français proposant l'alternative
agrégée.
"""
import re
from dataclasses import dataclass, field

from app.services.zone_matcher import normalize

# Jetons interdits quels que soient les autres mots de la colonne
BLOCK_TOKENS = {
    "prenom", "prenoms", "surnom",
    "telephone", "tel", "phone", "portable", "gsm", "whatsapp",
    "email", "mail", "courriel",
    "nin", "cni", "passeport", "nif",
    "naissance", "birth", "birthdate", "dob",
    "matricule", "immatriculation",
}
# Jetons désignant des personnes : interdits combinés à un identifiant
PERSON_TOKENS = {
    "beneficiaire", "beneficiaires", "personne", "personnes", "individu",
    "patient", "patients", "client", "clients", "menage", "menages",
    "chef", "contact", "responsable", "agent", "employe", "eleve",
    "enfant", "femme", "homme", "membre", "habitant",
}
IDENTITY_TOKENS = {"nom", "name", "id", "identifiant", "identite", "numero", "num", "no"}

PHONE_RE = re.compile(r"^\+?[\d][\d\s.\-()]{7,}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.IGNORECASE)


@dataclass
class PiiAlert:
    column: str
    level: str  # "block" | "warning"
    reason: str
    suggestion: str = ""


@dataclass
class PiiReport:
    alerts: list[PiiAlert] = field(default_factory=list)

    @property
    def blocked_columns(self) -> set[str]:
        return {a.column for a in self.alerts if a.level == "block"}

    def to_dict(self) -> list[dict]:
        return [a.__dict__ for a in self.alerts]


def _tokens(column_name: str) -> set[str]:
    return set(normalize(column_name).split())


def check_column_name(column: str) -> PiiAlert | None:
    tokens = _tokens(column)
    hit = tokens & BLOCK_TOKENS
    if hit:
        return PiiAlert(
            column=column,
            level="block",
            reason=f"La colonne « {column} » désigne une donnée personnelle ({', '.join(sorted(hit))}).",
            suggestion="Supprimez cette colonne du fichier ou remplacez-la par un "
            "agrégat par zone (ex. un nombre total par commune).",
        )
    if tokens & PERSON_TOKENS and tokens & IDENTITY_TOKENS:
        return PiiAlert(
            column=column,
            level="block",
            reason=f"La colonne « {column} » identifie des personnes (nom ou identifiant individuel).",
            suggestion="Comptez les personnes par zone plutôt que de les lister : "
            "ex. « beneficiaires_total » par commune, importé comme Indicateur.",
        )
    return None


def check_column_content(column: str, values: list) -> PiiAlert | None:
    """Heuristiques sur un échantillon de valeurs (téléphones, emails)."""
    sample = [str(v).strip() for v in values if v is not None and str(v).strip()]
    if len(sample) < 3:
        return None
    phone_like = sum(
        1 for v in sample
        if PHONE_RE.match(v) and (v.startswith("+") or re.search(r"[\s.\-()]", v))
        and len(re.sub(r"\D", "", v)) >= 8
    )
    email_like = sum(1 for v in sample if EMAIL_RE.match(v))
    if phone_like / len(sample) > 0.5:
        return PiiAlert(
            column=column,
            level="block",
            reason=f"Le contenu de « {column} » ressemble à des numéros de téléphone.",
            suggestion="Les coordonnées individuelles ne peuvent pas être importées. "
            "Conservez uniquement des données de sites ou des agrégats par zone.",
        )
    if email_like / len(sample) > 0.5:
        return PiiAlert(
            column=column,
            level="block",
            reason=f"Le contenu de « {column} » ressemble à des adresses email.",
            suggestion="Les coordonnées individuelles ne peuvent pas être importées.",
        )
    return None


def scan_dataframe(columns: list[str], rows: list[dict]) -> PiiReport:
    """Analyse noms de colonnes + échantillon de contenu (max 200 lignes)."""
    report = PiiReport()
    sample_rows = rows[:200]
    for col in columns:
        alert = check_column_name(col)
        if alert is None:
            alert = check_column_content(col, [r.get(col) for r in sample_rows])
        if alert:
            report.alerts.append(alert)
    return report


def filter_properties(props: dict) -> dict:
    """Retire des propriétés JSON toute clé de la liste noire."""
    clean = {}
    for key, value in props.items():
        if check_column_name(key) is None:
            clean[key] = value
    return clean
