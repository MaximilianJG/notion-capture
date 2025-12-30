"""
Notion endpoints - Auth status and data operations
Supports both Internal Integration (API key) and Public Integration (OAuth)
"""
import json
import urllib.parse
from typing import Optional
from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel

from app.services.notion.client import get_auth_status
from app.services.notion.pages import fetch_pages
from app.services.notion.databases import fetch_databases, fetch_database_properties
from app.services.notion.oauth import (
    get_auth_url as get_notion_auth_url,
    exchange_code_for_token,
    get_oauth_status,
    is_oauth_configured
)

router = APIRouter()


class NotionCredentials(BaseModel):
    """Notion credentials from frontend"""
    api_key: str
    selected_page_id: Optional[str] = None


def _get_access_token(header_value: Optional[str]) -> Optional[str]:
    """Extract access token from header - supports both raw token and JSON format"""
    if not header_value:
        return None
    # Try to parse as JSON (OAuth tokens stored as JSON)
    try:
        data = json.loads(header_value)
        return data.get("access_token")
    except (json.JSONDecodeError, TypeError):
        # Raw API key or token
        return header_value


@router.get("/auth/status")
def notion_auth_status_endpoint(
    x_notion_api_key: Optional[str] = Header(None, alias="X-Notion-Api-Key")
):
    """
    Check Notion connection status.
    Supports both Internal Integration API key and OAuth access token.
    """
    token = _get_access_token(x_notion_api_key)
    status = get_auth_status(token)
    # Add OAuth configuration info
    status["oauth_configured"] = is_oauth_configured()
    return status


@router.post("/auth/status")
def notion_auth_status_post(credentials: Optional[NotionCredentials] = None):
    """
    Check Notion connection status.
    Accepts API key in request body.
    """
    api_key = credentials.api_key if credentials else None
    status = get_auth_status(api_key)
    status["oauth_configured"] = is_oauth_configured()
    return status


# ============== OAuth Endpoints ==============

@router.get("/auth/url")
def notion_auth_url_endpoint():
    """
    Get Notion OAuth authorization URL.
    Returns URL and state for frontend to initiate OAuth flow.
    """
    result = get_notion_auth_url()
    if not result:
        return JSONResponse(
            status_code=500,
            content={
                "error": "Notion OAuth not configured. Set NOTION_CLIENT_ID and NOTION_CLIENT_SECRET.",
                "oauth_configured": False
            }
        )
    return result


@router.get("/auth/callback")
async def notion_auth_callback(request: Request):
    """
    Handle Notion OAuth callback.
    Exchanges code for access token and redirects to the app via custom URL scheme.
    """
    try:
        code = request.query_params.get('code')
        state = request.query_params.get('state')
        error = request.query_params.get('error')
        
        if error:
            return HTMLResponse(
                content=_create_notion_redirect_page(f"notioncapture://notion-callback?error={urllib.parse.quote(error)}"),
                status_code=200
            )
        
        if not code:
            return HTMLResponse(
                content=_create_notion_redirect_page("notioncapture://notion-callback?error=no_code"),
                status_code=200
            )
        
        # Exchange code for access token
        token_data = exchange_code_for_token(code)
        
        if not token_data:
            return HTMLResponse(
                content=_create_notion_redirect_page("notioncapture://notion-callback?error=token_exchange_failed"),
                status_code=200
            )
        
        # URL-encode the token data JSON for the redirect
        token_json = json.dumps(token_data)
        encoded_tokens = urllib.parse.quote(token_json)
        redirect_url = f"notioncapture://notion-callback?tokens={encoded_tokens}"
        
        # Return HTML page that auto-redirects to the app
        return HTMLResponse(content=_create_notion_redirect_page(redirect_url))
        
    except Exception as e:
        error_msg = urllib.parse.quote(str(e))
        return HTMLResponse(
            content=_create_notion_redirect_page(f"notioncapture://notion-callback?error={error_msg}"),
            status_code=200
        )


def _create_notion_redirect_page(redirect_url: str) -> str:
    """Create HTML page that redirects to the app via custom URL scheme"""
    is_error = "error=" in redirect_url
    title = "Error" if is_error else "Notion Connected!"
    message = "There was a problem connecting." if is_error else "Redirecting to Notion Capture..."
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{title}</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
                background: linear-gradient(135deg, #000000 0%, #191919 100%);
                color: white;
            }}
            .container {{
                text-align: center;
                padding: 40px;
            }}
            .spinner {{
                width: 50px;
                height: 50px;
                border: 4px solid rgba(255,255,255,0.3);
                border-top-color: white;
                border-radius: 50%;
                animation: spin 1s linear infinite;
                margin: 0 auto 20px;
            }}
            @keyframes spin {{
                to {{ transform: rotate(360deg); }}
            }}
            h1 {{ margin-bottom: 10px; }}
            p {{ opacity: 0.8; }}
            .manual-link {{
                margin-top: 30px;
                padding: 15px 30px;
                background: rgba(255,255,255,0.2);
                border-radius: 8px;
                display: inline-block;
            }}
            a {{
                color: white;
                text-decoration: none;
                font-weight: 500;
            }}
            a:hover {{ text-decoration: underline; }}
            .notion-logo {{
                font-size: 48px;
                margin-bottom: 20px;
            }}
        </style>
        <script>
            // Auto-redirect to app
            window.location.href = "{redirect_url}";
        </script>
    </head>
    <body>
        <div class="container">
            <div class="notion-logo">📝</div>
            {"" if is_error else '<div class="spinner"></div>'}
            <h1>{title}</h1>
            <p>{message}</p>
            <div class="manual-link">
                <a href="{redirect_url}">Click here if not redirected automatically</a>
            </div>
        </div>
    </body>
    </html>
    """


@router.post("/auth/logout")
def notion_auth_logout():
    """
    Logout from Notion - Frontend should clear stored tokens.
    This endpoint just confirms the action.
    """
    return {"status": "success", "message": "Clear tokens on frontend to complete logout"}


@router.get("/pages")
def get_notion_pages(
    x_notion_api_key: Optional[str] = Header(None, alias="X-Notion-Api-Key")
):
    """Get all accessible Notion pages"""
    token = _get_access_token(x_notion_api_key)
    if not token:
        return JSONResponse(status_code=400, content={"error": "No Notion token provided"})
    
    status = get_auth_status(token)
    if not status.get("connected"):
        return JSONResponse(status_code=400, content={"error": "Notion not connected"})
    
    pages = fetch_pages(token)
    return {"pages": pages, "count": len(pages)}


@router.get("/databases")
def get_notion_databases(
    page_id: Optional[str] = None,
    x_notion_api_key: Optional[str] = Header(None, alias="X-Notion-Api-Key"),
    x_notion_page_id: Optional[str] = Header(None, alias="X-Notion-Page-Id")
):
    """Get all databases, optionally filtered by parent page"""
    token = _get_access_token(x_notion_api_key)
    if not token:
        return JSONResponse(status_code=400, content={"error": "No Notion token provided"})
    
    status = get_auth_status(token)
    if not status.get("connected"):
        return JSONResponse(status_code=400, content={"error": "Notion not connected"})
    
    filter_page_id = page_id or x_notion_page_id
    databases = fetch_databases(token, filter_page_id)
    return {"databases": databases, "count": len(databases)}


@router.get("/databases/{database_id}/properties")
def get_database_properties_endpoint(
    database_id: str,
    x_notion_api_key: Optional[str] = Header(None, alias="X-Notion-Api-Key")
):
    """Get properties schema for a specific database"""
    token = _get_access_token(x_notion_api_key)
    if not token:
        return JSONResponse(status_code=400, content={"error": "No Notion token provided"})
    
    status = get_auth_status(token)
    if not status.get("connected"):
        return JSONResponse(status_code=400, content={"error": "Notion not connected"})
    
    properties = fetch_database_properties(token, database_id)
    return {"database_id": database_id, "properties": properties, "count": len(properties)}

