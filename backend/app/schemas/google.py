"""
Google-related schemas
"""
from typing import Optional
from pydantic import BaseModel


class GoogleAuthStatus(BaseModel):
    """Google authentication status"""
    connected: bool
    email: Optional[str] = None
    token_valid: bool = False
    error: Optional[str] = None
    has_credentials: bool = False


class GoogleAuthURL(BaseModel):
    """OAuth authorization URL response"""
    auth_url: str
    state: str


class GoogleCredentials(BaseModel):
    """Google OAuth credentials (stored by frontend)"""
    access_token: str
    refresh_token: Optional[str] = None
    token_uri: str = "https://oauth2.googleapis.com/token"
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    expiry: Optional[str] = None


class GoogleCallbackRequest(BaseModel):
    """OAuth callback data"""
    code: str
    state: str

