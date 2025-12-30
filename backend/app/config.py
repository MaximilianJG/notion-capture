"""
Application Configuration
All settings loaded from environment variables.
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings from environment variables"""
    
    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    
    # Google OAuth (server-side config for OAuth flow)
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None
    google_redirect_uri: str = "http://127.0.0.1:8000/google/auth/callback"
    
    # Notion OAuth (Public Integration)
    notion_client_id: Optional[str] = None
    notion_client_secret: Optional[str] = None
    notion_redirect_uri: str = "http://localhost:8000/notion/auth/callback"
    
    # Server
    debug: bool = False
    cors_origins: str = "*"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


# Global settings instance
settings = Settings()


def get_openai_api_key() -> str:
    """Get OpenAI API key - from env or settings"""
    return os.getenv("OPENAI_API_KEY", settings.openai_api_key)

