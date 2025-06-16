from pydantic_settings import BaseSettings
import os


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://username:password@localhost/supercpe_v2"

    # API
    api_title: str = "SuperCPE v2"
    api_version: str = "2.0.0"

    # Security
    secret_key: str = "your-secret-key-change-in-production"

    # State-specific settings (for multi-state deployment)
    state_code: str = "NH"

    # Digital Ocean Spaces - ADD ALL MISSING FIELDS
    do_spaces_region: str = "nyc3"
    do_spaces_bucket: str = "supercpe-certificates"
    do_spaces_access_key: str = ""
    do_spaces_secret_key: str = ""
    do_spaces_endpoint: str = "https://nyc3.digitaloceanspaces.com"

    # Environment
    environment: str = "development"

    class Config:
        env_file = ".env"
        extra = "ignore"  # This allows extra environment variables without errors


settings = Settings()
