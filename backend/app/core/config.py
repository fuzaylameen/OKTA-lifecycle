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

    # User JWT & Authentication Settings
    USER_JWT_SECRET: str = "intelliid-super-secure-jwt-secret-key-change-in-production"
    USER_JWT_ALGORITHM: str = "HS256"
    USER_JWT_ISSUER: str = "intelliid-auth"
    USER_JWT_AUDIENCE: str = "intelliid-api"
    USER_JWT_EXPIRE_MINUTES: int = 60

    # Optional Okta / External Auth Settings
    OKTA_ISSUER: str = ""
    OKTA_AUDIENCE: str = ""
    OKTA_ROLE_CLAIM: str = "role"
    OKTA_SSL_VERIFY: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()