"""Configuration de l'application (variables d'environnement)."""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Plateforme d'intégration de données — Niger"
    database_url: str = "postgresql+psycopg2://niger:niger@localhost:5432/niger_data"
    upload_dir: str = "uploads"
    # Fournisseur LLM : "anthropic" (nécessite ANTHROPIC_API_KEY) ou "mock"
    llm_provider: str = "mock"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-5"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
