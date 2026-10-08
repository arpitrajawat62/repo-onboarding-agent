from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    app_name: str = "Repo Onboarding Agent"
    environment: str = "dev"

    # CORS
    allowed_origins: list[str] = ["http://localhost:3000"]


    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""

    # Grok
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"


settings = Settings()