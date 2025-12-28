"""
Google OAuth - Stateless authentication
Tokens are managed by the frontend, backend just processes them
"""
import os
import json
import secrets
from typing import Dict, Any, Optional
from datetime import datetime

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from app.config import settings

# OAuth configuration
SCOPES = ['https://www.googleapis.com/auth/calendar']


def _get_client_config() -> Optional[Dict[str, Any]]:
    """Get Google OAuth client configuration"""
    # Try environment variables first
    if settings.google_client_id and settings.google_client_secret:
        return {
            "web": {
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [settings.google_redirect_uri]
            }
        }
    
    # Try client_secret.json file
    client_secret_file = os.getenv("GOOGLE_CLIENT_SECRETS_FILE", "client_secret.json")
    if os.path.exists(client_secret_file):
        with open(client_secret_file) as f:
            return json.load(f)
    
    return None


def get_auth_url() -> Optional[Dict[str, str]]:
    """Generate Google OAuth authorization URL"""
    client_config = _get_client_config()
    if not client_config:
        return None
    
    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)
    
    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=settings.google_redirect_uri
    )
    
    authorization_url, _ = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent',
        state=state
    )
    
    return {
        "auth_url": authorization_url,
        "state": state
    }


def exchange_code_for_tokens(code: str, state: str) -> Optional[Dict[str, Any]]:
    """Exchange authorization code for tokens - returns tokens for frontend to store"""
    client_config = _get_client_config()
    if not client_config:
        return None
    
    try:
        flow = Flow.from_client_config(
            client_config,
            scopes=SCOPES,
            redirect_uri=settings.google_redirect_uri
        )
        
        flow.fetch_token(code=code)
        credentials = flow.credentials
        
        # Return tokens for frontend to store
        return {
            "access_token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "expiry": credentials.expiry.isoformat() if credentials.expiry else None,
            "scopes": list(credentials.scopes) if credentials.scopes else SCOPES
        }
    except Exception as e:
        print(f"Token exchange error: {e}")
        return None


def refresh_access_token(
    refresh_token: str,
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Refresh access token using refresh token"""
    # Get client config for refresh
    client_config = _get_client_config()
    if not client_config:
        return None
    
    web_config = client_config.get("web", client_config.get("installed", {}))
    
    try:
        credentials = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id or web_config.get("client_id"),
            client_secret=client_secret or web_config.get("client_secret")
        )
        
        credentials.refresh(GoogleRequest())
        
        return {
            "access_token": credentials.token,
            "refresh_token": credentials.refresh_token or refresh_token,
            "expiry": credentials.expiry.isoformat() if credentials.expiry else None
        }
    except Exception as e:
        print(f"Token refresh error: {e}")
        return None


def build_credentials_from_tokens(tokens: Dict[str, Any]) -> Optional[Credentials]:
    """Build Credentials object from token dictionary"""
    if not tokens or not tokens.get("access_token"):
        return None
    
    try:
        expiry = None
        if tokens.get("expiry"):
            expiry = datetime.fromisoformat(tokens["expiry"].replace("Z", "+00:00"))
        
        credentials = Credentials(
            token=tokens["access_token"],
            refresh_token=tokens.get("refresh_token"),
            token_uri=tokens.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=tokens.get("client_id"),
            client_secret=tokens.get("client_secret"),
            expiry=expiry
        )
        
        # Refresh if expired
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(GoogleRequest())
        
        return credentials if credentials.valid else None
        
    except Exception as e:
        print(f"Build credentials error: {e}")
        return None


def get_auth_status(tokens: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Get Google auth status from tokens"""
    if not tokens or not tokens.get("access_token"):
        return {
            "connected": False,
            "email": None,
            "token_valid": False,
            "error": "No tokens provided",
            "has_credentials": False
        }
    
    credentials = build_credentials_from_tokens(tokens)
    if not credentials or not credentials.valid:
        return {
            "connected": False,
            "email": None,
            "token_valid": False,
            "error": "Token expired or invalid",
            "has_credentials": True
        }
    
    # Try to get user email
    email = None
    try:
        service = build('calendar', 'v3', credentials=credentials)
        calendar_list = service.calendarList().list(maxResults=1).execute()
        
        if calendar_list.get('items'):
            calendar_id = calendar_list['items'][0].get('id')
            if '@' in str(calendar_id):
                email = calendar_id
    except Exception as e:
        print(f"Error getting Google user info: {e}")
    
    return {
        "connected": True,
        "email": email,
        "token_valid": True,
        "error": None,
        "has_credentials": True
    }

