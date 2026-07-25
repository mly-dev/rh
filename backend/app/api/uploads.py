"""Ingestion : upload, prévisualisation, mapping et import."""
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.models import DataSource
from app.services.ingestion import ImportError_, preview_source, run_import
from app.services.parsing import ParsingError, detect_file_type

router = APIRouter(prefix="/api", tags=["ingestion"])


def _source_or_404(db: Session, source_id: int) -> DataSource:
    source = db.get(DataSource, source_id)
    if source is None:
        raise HTTPException(404, "Source introuvable.")
    return source


def _source_dict(s: DataSource) -> dict:
    return {
        "id": s.id,
        "filename": s.filename,
        "file_type": s.file_type,
        "uploaded_by": s.uploaded_by,
        "uploaded_at": s.uploaded_at.isoformat() if s.uploaded_at else None,
        "status": s.status,
        "domain": s.domain,
        "row_count": s.row_count,
        "report": s.parse_report,
    }


@router.post("/uploads")
async def upload_file(
    file: UploadFile = File(...),
    uploaded_by: str = Form("anonyme"),
    domain: str = Form("autre"),
    db: Session = Depends(get_db),
):
    """Téléverse un fichier et retourne sa prévisualisation."""
    try:
        file_type = detect_file_type(file.filename or "")
    except ParsingError as exc:
        raise HTTPException(400, str(exc)) from exc

    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored = upload_dir / f"{uuid.uuid4().hex}_{Path(file.filename).name}"
    content = await file.read()
    stored.write_bytes(content)

    source = DataSource(
        filename=Path(file.filename).name,
        file_type=file_type,
        uploaded_by=uploaded_by,
        domain=domain,
        stored_path=str(stored),
    )
    db.add(source)
    db.commit()

    try:
        result = preview_source(source)
    except ParsingError as exc:
        source.status = "failed"
        source.parse_report = {"error": str(exc)}
        db.commit()
        raise HTTPException(400, str(exc)) from exc

    source.row_count = result["preview"]["row_count"]
    source.parse_report = {
        "columns": result["preview"]["columns"],
        "pii_alerts": result["pii_alerts"],
    }
    db.commit()
    return {"source": _source_dict(source), **result}


@router.get("/uploads/{source_id}/preview")
def get_preview(source_id: int, db: Session = Depends(get_db)):
    source = _source_or_404(db, source_id)
    try:
        result = preview_source(source)
    except ParsingError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"source": _source_dict(source), **result}


class ImportRequest(BaseModel):
    entity: str
    mappings: dict[str, str]  # colonne source → champ cible
    defaults: dict[str, str] = {}
    include_extra: bool = True


@router.post("/uploads/{source_id}/import")
def import_source(
    source_id: int, payload: ImportRequest, db: Session = Depends(get_db)
):
    source = _source_or_404(db, source_id)
    if source.status == "imported":
        raise HTTPException(409, "Cette source a déjà été importée.")
    try:
        report = run_import(
            db,
            source,
            payload.entity,
            payload.mappings,
            payload.defaults,
            payload.include_extra,
        )
    except ImportError_ as exc:
        raise HTTPException(400, str(exc)) from exc
    except ParsingError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"source": _source_dict(source), "report": report.to_dict()}


@router.get("/sources")
def list_sources(db: Session = Depends(get_db)):
    """Traçabilité : tous les fichiers importés."""
    sources = db.query(DataSource).order_by(DataSource.uploaded_at.desc()).all()
    return [_source_dict(s) for s in sources]
