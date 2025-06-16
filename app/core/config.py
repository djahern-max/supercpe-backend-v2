from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://username:password@localhost/supercpe_v2"
    
    # API
    api_title: str = "SuperCPE v2"
    api_version: str = "2.0.0"
    
    # Security
    secret_key: str = "your-secret-key-change-in-production"
    
    class Config:
        env_file = ".env"

settings = Settings()
