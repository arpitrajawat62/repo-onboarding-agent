from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    # App
    app_name: str = "Repo Onboarding Agent"
    environment: str = "dev"

    # CORS
    allowed_origins: list[str] = ["http://localhost:3000"]


    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""

    # Grok
    grok_api_key: str = ""
    grok_model: str = "llama-3.3-70b-versatile"


Settings = Settings()