from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# config.py → core → app → backend → repo root
REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Runtime configuration from NEBULA_* environment variables or backend/.env."""

    model_config = SettingsConfigDict(env_prefix="NEBULA_", env_file=".env", extra="ignore")

    data_dir: Path = REPO_ROOT / "data" / "derived"
    cors_origins: list[str] = ["http://localhost:5173"]
