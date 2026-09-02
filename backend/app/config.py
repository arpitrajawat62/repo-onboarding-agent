from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    app_name: str = "Repo onboarding Agent"
    environment: str = "dev"


    allowed_origins: list[str] = ["http://localhost:3000"]


Settings = Settings()