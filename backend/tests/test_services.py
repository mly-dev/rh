"""Tests unitaires : parsing, garde-fou PII, correspondance de zones."""
import pandas as pd

from app.services import pii_guard
from app.services.parsing import build_preview, infer_column_type, parse_file
from app.services.zone_matcher import ZoneMatcher, normalize


class TestParsing:
    def test_csv_virgule(self):
        df = parse_file("test.csv", b"nom,quantite\nSite A,10\nSite B,20\n")
        assert list(df.columns) == ["nom", "quantite"]
        assert len(df) == 2

    def test_csv_point_virgule(self):
        df = parse_file("test.csv", "nom;région\nCSI Ouallam;Tillabéri\n".encode())
        assert list(df.columns) == ["nom", "région"]

    def test_xlsx(self, tmp_path):
        path = tmp_path / "t.xlsx"
        pd.DataFrame({"site": ["A"], "capacite": [5]}).to_excel(path, index=False)
        df = parse_file("t.xlsx", path.read_bytes())
        assert list(df.columns) == ["site", "capacite"]

    def test_format_refuse(self):
        import pytest

        from app.services.parsing import ParsingError

        with pytest.raises(ParsingError):
            parse_file("donnees.docx", b"xxx")

    def test_inference_types(self):
        assert infer_column_type(pd.Series(["1", "2", "3"])) == "int"
        assert infer_column_type(pd.Series(["1,5", "2.7"])) == "float"
        assert infer_column_type(pd.Series(["12/01/2025", "13/01/2025"])) == "date"
        assert infer_column_type(pd.Series(["abc", "def"])) == "str"

    def test_preview(self):
        df = parse_file("t.csv", b"a,b\n1,x\n2,y\n")
        preview = build_preview(df)
        assert preview["row_count"] == 2
        assert preview["columns"][0] == {"name": "a", "type": "int"}


class TestPiiGuard:
    def test_colonnes_interdites(self):
        for col in ["telephone", "Prénom", "email_contact", "date_naissance", "NIN"]:
            alert = pii_guard.check_column_name(col)
            assert alert is not None and alert.level == "block", col

    def test_nom_de_personne_bloque(self):
        assert pii_guard.check_column_name("nom_beneficiaire").level == "block"
        assert pii_guard.check_column_name("id_patient").level == "block"

    def test_colonnes_autorisees(self):
        for col in ["nom_site", "beneficiaires_total", "quantite", "region",
                    "nombre_menages", "id_site"]:
            assert pii_guard.check_column_name(col) is None, col

    def test_contenu_telephone(self):
        alert = pii_guard.check_column_content(
            "contact_col", ["+227 96 12 34 56", "+227 90 11 22 33", "+227 99 88 77 66"]
        )
        assert alert is not None and alert.level == "block"

    def test_contenu_numerique_ok(self):
        assert pii_guard.check_column_content("qte", ["1250", "800", "43"]) is None

    def test_filtre_properties(self):
        clean = pii_guard.filter_properties(
            {"telephone": "x", "categorie": "vivres", "email": "a@b.c"}
        )
        assert clean == {"categorie": "vivres"}


class TestZoneMatcher:
    def test_normalisation(self):
        assert normalize("Tillabéri") == "tillaberi"
        assert normalize("N'Guigmi") == "n guigmi"
        assert normalize("  MARADI ") == "maradi"

    def test_correspondance_exacte_et_accents(self, db):
        matcher = ZoneMatcher(db)
        assert matcher.match("Tillaberi").name == "Tillabéri"
        assert matcher.match("DIFFA").level in ("commune", "departement", "region")

    def test_correspondance_floue(self, db):
        matcher = ZoneMatcher(db)
        zone = matcher.match("Tilaberi")  # faute de frappe
        assert zone is not None and normalize(zone.name) == "tillaberi"

    def test_zone_inconnue(self, db):
        assert ZoneMatcher(db).match("Tombouctou") is None

    def test_niveau_impose(self, db):
        matcher = ZoneMatcher(db)
        assert matcher.match("Zinder", level="region").level == "region"
