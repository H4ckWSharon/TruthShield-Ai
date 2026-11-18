from pydantic_settings import BaseSettings
from typing import List, Optional
from pathlib import Path
import os
import warnings

_BASE_DIR = Path(__file__).resolve().parent.parent.parent
_DEFAULT_STORAGE = (
    _BASE_DIR.parent / "storage"
    if (_BASE_DIR.parent / "docker-compose.yml").exists()
    else _BASE_DIR / "storage"
)

class Settings(BaseSettings):
    APP_NAME: str = "TruthShield AI"
    APP_VERSION: str = "2.0.0"
    COMPANY_NAME: str = "Alphard Crucis Private Limited"
    TAGLINE: str = "Together for a Safer Digital World"
    ENV: str = "development"
    DEBUG: bool = True

    # Authentication Mode
    # False = Direct-access workstation mode (no login/signup required)
    # True  = Strict JWT authentication required on protected endpoints
    REQUIRE_AUTH: bool = False

    # Security
    SECRET_KEY: str = "truthshield-dev-secret-key-alphard-crucis-2026-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    EVIDENCE_ENCRYPTION_KEY: Optional[str] = None
    RATE_LIMIT_RPM: int = 180

    # Database (SQLite zero-config default; supports PostgreSQL via DATABASE_URL)
    DATABASE_URL: str = f"sqlite:///{(_BASE_DIR / 'truthshield.db').as_posix()}"

    # Redis & Background Workers
    REDIS_URL: str = "redis://localhost:6379/0"

    # Storage Paths
    BASE_DIR: Path = _BASE_DIR
    STORAGE_DIR: Path = Path(os.getenv("STORAGE_DIR", str(_DEFAULT_STORAGE)))

    @property
    def EVIDENCE_DIR(self) -> Path:
        return self.STORAGE_DIR / "evidence"

    @property
    def REPORTS_DIR(self) -> Path:
        return self.STORAGE_DIR / "reports"

    @property
    def REFERENCE_DIR(self) -> Path:
        return self.STORAGE_DIR / "reference"

    @property
    def sqlalchemy_database_uri(self) -> str:
        """Normalize postgresql:// URLs to use psycopg v3 driver cleanly."""
        url = self.DATABASE_URL
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url

    # AI & Local Inference
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2"
    OLLAMA_VISION_MODEL: str = "llava"
    WHISPER_MODEL_SIZE: str = "tiny"
    AI_TIMEOUT_SECONDS: int = 15

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3100",
        "http://127.0.0.1:3100",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:8100",
        "http://127.0.0.1:8100",
    ]

    # Max Upload Size: 50MB
    MAX_UPLOAD_SIZE_BYTES: int = 50 * 1024 * 1024

    # SSRF Protection: Block internal and private IPs
    BLOCKED_IP_NETWORKS: List[str] = [
        "127.0.0.0/8",      # Loopback
        "10.0.0.0/8",       # Private Class A
        "172.16.0.0/12",    # Private Class B
        "192.168.0.0/16",   # Private Class C
        "169.254.0.0/16",   # Link-local / Cloud Metadata (AWS, GCP, Azure)
        "::1/128",          # IPv6 loopback
        "fc00::/7",         # IPv6 Unique Local Address
        "fe80::/10"         # IPv6 Link-local
    ]

    # Feature Flags
    ENABLE_OLLAMA: bool = True
    ENABLE_FINGERPRINTING: bool = True
    ENABLE_REMOVAL_ASSISTANCE: bool = True
    ENABLE_PDF_REPORTS: bool = True
    ENABLE_AUDIO_TRANSCRIPTION: bool = True

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore"
    }

settings = Settings()

if settings.ENV.lower() == "production" and "change-in-production" in settings.SECRET_KEY:
    warnings.warn(
        "TruthShield AI is running in production mode with the default development SECRET_KEY. "
        "Set a strong random SECRET_KEY environment variable!",
        RuntimeWarning,
    )

# Ensure storage directories exist
settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
settings.EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
settings.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
settings.REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
