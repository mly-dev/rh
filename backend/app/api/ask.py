"""Interrogation en langage naturel (RAG)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models import RagQuery
from app.rag.nl2query import answer_question

router = APIRouter(prefix="/api", tags=["rag"])


class AskRequest(BaseModel):
    question: str


@router.post("/ask")
def ask(payload: AskRequest, db: Session = Depends(get_db)):
    question = payload.question.strip()
    if not question:
        raise HTTPException(400, "La question est vide.")
    return answer_question(db, question)


@router.get("/ask/history")
def history(db: Session = Depends(get_db)):
    rows = db.query(RagQuery).order_by(RagQuery.created_at.desc()).limit(50).all()
    return [
        {
            "id": r.id,
            "question": r.question,
            "answer": r.answer,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
