from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    OKTA_DOMAIN: str
    OKTA_CLIENT_ID: str
    OKTA_PRIVATE_KEY_PATH: str

    DATABASE_URL: str = "sqlite:///./intelliid.db"

    FRONTEND_URL: str = "http://localhost:5173"

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True
    )


settings = Settings()