"""Point d'entrée FastAPI — Plateforme d'intégration de données (Niger)."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import ask, dashboard, objects, uploads, zones
from app.core.config import settings
from app.core.db import SessionLocal, init_db
from app.services.seed import seed_zones

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # MVP — à restreindre en production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(zones.router)
app.include_router(uploads.router)
app.include_router(objects.router)
app.include_router(dashboard.router)
app.include_router(ask.router)


@app.on_event("startup")
def startup() -> None:
    init_db()
    db = SessionLocal()
    try:
        seed_zones(db)
    finally:
        db.close()


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "app": settings.app_name}
