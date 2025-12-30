"""
Notion OAuth - Public Integration authentication
Allows users to connect their own Notion workspace via OAuth flow.
"""
import base64
import secrets
import requests
import urllib.parse
from typing import Dict, Any, Optional

from app.config import settings

# Notion OAuth endpoints
NOTION_AUTH_URL = "https://api.notion.com/v1/oauth/authorize"
NOTION_TOKEN_URL = "https://api.notion.com/v1/oauth/token"
NOTION_API_VERSION = "2022-06-28"


def get_auth_url() -> Optional[Dict[str, str]]:
    """Generate Notion OAuth authorization URL"""
    if not settings.notion_client_id:
        return None
    
    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)
    
    # URL-encode the redirect URI
    encoded_redirect_uri = urllib.parse.quote(settings.notion_redirect_uri, safe='')
    
    # Build authorization URL
    auth_url = (
        f"{NOTION_AUTH_URL}"
        f"?client_id={settings.notion_client_id}"
        f"&response_type=code"
        f"&owner=user"
        f"&redirect_uri={encoded_redirect_uri}"
        f"&state={state}"
    )
    
    return {
        "auth_url": auth_url,
        "state": state
    }


def exchange_code_for_token(code: str) -> Optional[Dict[str, Any]]:
    """Exchange authorization code for access token"""
    if not settings.notion_client_id or not settings.notion_client_secret:
        return None
    
    try:
        # Notion requires Basic auth with client_id:client_secret
        credentials = f"{settings.notion_client_id}:{settings.notion_client_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/json",
            "Notion-Version": NOTION_API_VERSION
        }
        
        body = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.notion_redirect_uri
        }
        
        response = requests.post(
            NOTION_TOKEN_URL,
            headers=headers,
            json=body,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            # Return token data for frontend to store
            return {
                "access_token": data.get("access_token"),
                "token_type": data.get("token_type", "bearer"),
                "bot_id": data.get("bot_id"),
                "workspace_id": data.get("workspace_id"),
                "workspace_name": data.get("workspace_name"),
                "workspace_icon": data.get("workspace_icon"),
                "owner": data.get("owner"),
                "duplicated_template_id": data.get("duplicated_template_id")
            }
        else:
            print(f"Notion token exchange error: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"Notion token exchange exception: {e}")
        return None


def get_oauth_status(access_token: Optional[str]) -> Dict[str, Any]:
    """Check if OAuth token is valid by testing the connection"""
    if not access_token:
        return {
            "connected": False,
            "workspace_name": None,
            "error": "No access token provided",
            "setup_required": True,
            "oauth_configured": bool(settings.notion_client_id)
        }
    
    try:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Notion-Version": NOTION_API_VERSION
        }
        
        response = requests.get(
            "https://api.notion.com/v1/users/me",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            user_data = response.json()
            return {
                "connected": True,
                "workspace_name": user_data.get("name", "Notion"),
                "type": user_data.get("type", "bot"),
                "error": None,
                "setup_required": False,
                "oauth_configured": True
            }
        elif response.status_code == 401:
            return {
                "connected": False,
                "workspace_name": None,
                "error": "Token expired or invalid",
                "setup_required": True,
                "oauth_configured": True
            }
        else:
            return {
                "connected": False,
                "workspace_name": None,
                "error": f"API error: {response.status_code}",
                "setup_required": True,
                "oauth_configured": True
            }
    except Exception as e:
        return {
            "connected": False,
            "workspace_name": None,
            "error": str(e),
            "setup_required": True,
            "oauth_configured": bool(settings.notion_client_id)
        }


def is_oauth_configured() -> bool:
    """Check if Notion OAuth is configured"""
    return bool(settings.notion_client_id and settings.notion_client_secret)

