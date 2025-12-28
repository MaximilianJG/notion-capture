"""
Credential schemas - Frontend sends these with requests
"""
from typing import Optional
from pydantic import BaseModel


class NotionCredentials(BaseModel):
    """Notion API credentials from frontend"""
    api_key: str
    selected_page_id: Optional[str] = None


class GoogleCredentials(BaseModel):
    """Google OAuth credentials from frontend"""
    access_token: str
    refresh_token: Optional[str] = None
    token_uri: str = "https://oauth2.googleapis.com/token"
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    expiry: Optional[str] = None  # ISO datetime string


class RequestCredentials(BaseModel):
    """Combined credentials that frontend sends with capture requests"""
    notion: Optional[NotionCredentials] = None
    google: Optional[GoogleCredentials] = None

