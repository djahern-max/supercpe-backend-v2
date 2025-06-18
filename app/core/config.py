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

    # State-specific settings
    state_code: str = "NH"

    # Digital Ocean Spaces
    do_spaces_region: str = "nyc3"
    do_spaces_bucket: str = "supercpe-certificates"
    do_spaces_access_key: str = ""
    do_spaces_secret_key: str = ""
    do_spaces_endpoint: str = "https://nyc3.digitaloceanspaces.com"

    # Stripe Configuration
    stripe_publishable_key: str = ""
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_mode: str = "test"
    stripe_price_id_monthly: str = ""  # New: Price ID for monthly subscription
    stripe_price_id_annual: str = ""  # New: Price ID for annual subscription

    # Google Cloud Vision - NEW SETTINGS
    google_cloud_project: str = ""
    google_application_credentials: str = "/app/gcp-service-account.json"
    gcv_enabled: bool = True

    # Google OAuth - NEW SETTINGS
    google_client_id: str = ""
    google_client_secret: str = ""

    # Frontend URL - NEW SETTING
    frontend_url: str = "https://nh.supercpe.com"

    # Environment
    environment: str = "development"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
