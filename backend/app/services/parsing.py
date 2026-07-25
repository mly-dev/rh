"""Parsing des fichiers CSV, Excel (.xlsx) et PDF (tableaux).

Produit un aperçu uniforme : colonnes, types inférés, lignes d'exemple.
"""
import io
from pathlib import Path

import pandas as pd


class ParsingError(Exception):
    pass


def detect_file_type(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".csv":
        return "csv"
    if ext in (".xlsx", ".xls"):
        return "xlsx"
    if ext == ".pdf":
        return "pdf"
    raise ParsingError(
        f"Format non pris en charge : {ext or 'inconnu'}. "
        "Formats acceptés : CSV, Excel (.xlsx), PDF (tableaux)."
    )


def _read_csv(content: bytes) -> pd.DataFrame:
    for sep in (None, ";", ","):
        try:
            df = pd.read_csv(
                io.BytesIO(content), sep=sep, engine="python", dtype=str,
                skip_blank_lines=True,
            )
            if len(df.columns) > 1 or sep == ",":
                return df
        except Exception:  # noqa: BLE001 — on essaie le séparateur suivant
            continue
    raise ParsingError("Impossible de lire le fichier CSV (séparateur non détecté).")


def _read_xlsx(content: bytes) -> pd.DataFrame:
    try:
        return pd.read_excel(io.BytesIO(content), dtype=str)
    except Exception as exc:  # noqa: BLE001
        raise ParsingError(f"Impossible de lire le fichier Excel : {exc}") from exc


def _read_pdf(content: bytes) -> pd.DataFrame:
    import pdfplumber

    frames: list[pd.DataFrame] = []
    header: list[str] | None = None
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages:
                for table in page.extract_tables():
                    if not table or len(table) < 2:
                        continue
                    if header is None:
                        header = [str(c or "").strip() for c in table[0]]
                        rows = table[1:]
                    else:
                        first = [str(c or "").strip() for c in table[0]]
                        rows = table[1:] if first == header else table
                    frames.append(pd.DataFrame(rows, columns=header))
    except Exception as exc:  # noqa: BLE001
        raise ParsingError(f"Impossible de lire le PDF : {exc}") from exc
    if not frames:
        raise ParsingError(
            "Aucun tableau détecté dans le PDF. Seuls les PDF contenant des "
            "tableaux structurés peuvent être importés."
        )
    return pd.concat(frames, ignore_index=True).astype(str)


def parse_file(filename: str, content: bytes) -> pd.DataFrame:
    file_type = detect_file_type(filename)
    reader = {"csv": _read_csv, "xlsx": _read_xlsx, "pdf": _read_pdf}[file_type]
    df = reader(content)
    df.columns = [str(c).strip() for c in df.columns]
    df = df.dropna(how="all").reset_index(drop=True)
    if df.empty:
        raise ParsingError("Le fichier ne contient aucune ligne de données.")
    return df


def infer_column_type(series: pd.Series) -> str:
    """Infère le type d'une colonne lue en texte : int, float, date ou str."""
    values = series.dropna().astype(str).str.strip()
    values = values[values != ""]
    if values.empty:
        return "str"
    numeric = pd.to_numeric(values.str.replace(",", ".", regex=False), errors="coerce")
    if numeric.notna().mean() > 0.9:
        return "int" if (numeric.dropna() % 1 == 0).all() else "float"
    dates = pd.to_datetime(values, errors="coerce", dayfirst=True, format="mixed")
    if dates.notna().mean() > 0.9:
        return "date"
    return "str"


def build_preview(df: pd.DataFrame, max_rows: int = 20) -> dict:
    columns = [
        {"name": col, "type": infer_column_type(df[col])} for col in df.columns
    ]
    head = df.head(max_rows).astype(object)
    rows = head.where(pd.notna(head), None).to_dict(orient="records")
    return {
        "columns": columns,
        "rows": rows,
        "row_count": int(len(df)),
    }
