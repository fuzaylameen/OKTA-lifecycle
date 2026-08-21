from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    OKTA_DOMAIN: str
    OKTA_CLIENT_ID: str
    OKTA_PRIVATE_KEY_PATH: str

    DATABASE_URL: str = "sqlite:///./intelliid.db"

    FRONTEND_URL: str = "http://localhost:5173"

    # Password expiry settings
    PASSWORD_EXPIRY_DAYS: int = 90
    PASSWORD_EXPIRY_WARNING_DAYS: int = 14

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True
    )


settings = Settings()