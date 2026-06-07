import os
from typing import Any, Dict, Optional
from pydantic import PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Krishi-Vani Core AI Backend"
    API_V1_STR: str = "/api/v1"
    ENV: str = "development"
    DEBUG: bool = False  # Explicitly off by default; set DEBUG=true in .env for local dev
    SECRET_KEY: str = ""  # REQUIRED — set a strong random value in .env
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # Internal admin API key — protects endpoints like /sms/send from public access.
    # Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
    INTERNAL_API_KEY: str = ""  # REQUIRED in production; leave empty to disable the endpoint

    # If True, validate X-Twilio-Signature on all webhook endpoints.
    # Set to False ONLY during local development without ngrok.
    TWILIO_WEBHOOK_VALIDATION: bool = True

    # Database Settings
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "krishi_db"
    POSTGRES_PORT: int = 5432
    SQLALCHEMY_DATABASE_URI: Optional[str] = None

    @field_validator("SQLALCHEMY_DATABASE_URI", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: Optional[str], info: Any) -> Any:
        if isinstance(v, str) and v:
            return v
        data = info.data
        user = data.get("POSTGRES_USER")
        password = data.get("POSTGRES_PASSWORD")
        server = data.get("POSTGRES_SERVER")
        port = data.get("POSTGRES_PORT")
        db = data.get("POSTGRES_DB")
        return f"postgresql+asyncpg://{user}:{password}@{server}:{port}/{db}"

    # Sync Database URI (for migrations / sync tasks)
    SQLALCHEMY_DATABASE_URI_SYNC: Optional[str] = None

    @field_validator("SQLALCHEMY_DATABASE_URI_SYNC", mode="before")
    @classmethod
    def assemble_sync_db_connection(cls, v: Optional[str], info: Any) -> Any:
        if isinstance(v, str) and v:
            return v
        data = info.data
        user = data.get("POSTGRES_USER")
        password = data.get("POSTGRES_PASSWORD")
        server = data.get("POSTGRES_SERVER")
        port = data.get("POSTGRES_PORT")
        db = data.get("POSTGRES_DB")
        return f"postgresql://{user}:{password}@{server}:{port}/{db}"

    # Redis & Celery Settings
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    # AI API Keys
    GEMINI_API_KEY: str = ""
    OPENWEATHERMAP_API_KEY: str = ""
    BHASHINI_API_KEY: str = ""
    BHASHINI_USER_ID: str = ""
    BHASHINI_APP_ID: str = ""

    # Telephony Configuration
    BASE_URL: str = "http://localhost:8000"
    TELEPHONY_PROVIDER: str = "twilio"  # "twilio" or "exotel"

    # Twilio API credentials
    TWILIO_ACCOUNT_SID: str = "your_twilio_account_sid_here"
    TWILIO_AUTH_TOKEN: str = "your_twilio_auth_token_here"
    TWILIO_PHONE_NUMBER: str = "your_twilio_phone_number_here"

    # Exotel API credentials
    EXOTEL_API_KEY: str = "your_exotel_api_key_here"
    EXOTEL_API_TOKEN: str = "your_exotel_api_token_here"
    EXOTEL_SUBDOMAIN: str = "api.exotel.com"
    EXOTEL_VIRTUAL_NUMBER: str = "your_exotel_virtual_number_here"

    # Geolocation Fallbacks
    DEFAULT_LATITUDE: float = 25.611
    DEFAULT_LONGITUDE: float = 85.144
    DEFAULT_DISTRICT: str = "Patna"
    DEFAULT_STATE: str = "Bihar"
    DEFAULT_BLOCK: str = "Phulwari Sharif"

    # Directory Settings
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    DATA_DIR: str = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
    FAISS_INDEX_PATH: str = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "faiss_index"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

settings = Settings()

# Ensure directories exist
os.makedirs(settings.DATA_DIR, exist_ok=True)
