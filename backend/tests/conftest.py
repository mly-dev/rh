import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Base SQLite jetable pour les tests (avant tout import de l'application)
_TEST_DB = Path(__file__).parent / "test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB}"
os.environ["UPLOAD_DIR"] = str(Path(__file__).parent / "uploads_test")
os.environ["LLM_PROVIDER"] = "mock"

from fastapi.testclient import TestClient  # noqa: E402

from app.core.db import SessionLocal, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.services.seed import seed_zones  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _database():
    if _TEST_DB.exists():
        _TEST_DB.unlink()
    init_db()
    db = SessionLocal()
    seed_zones(db)
    db.close()
    yield
    if _TEST_DB.exists():
        _TEST_DB.unlink()


@pytest.fixture()
def db():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c
