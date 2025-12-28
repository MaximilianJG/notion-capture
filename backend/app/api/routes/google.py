"""
Google OAuth and Calendar endpoints
"""
import json
from typing import Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Request, Header
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel

from app.services.google import (
    get_auth_url,
    exchange_code_for_tokens,
    get_auth_status,
    create_calendar_event,
    delete_calendar_event
)

router = APIRouter()


class GoogleTokens(BaseModel):
    """Google OAuth tokens from frontend"""
    access_token: str
    refresh_token: Optional[str] = None
    token_uri: str = "https://oauth2.googleapis.com/token"
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    expiry: Optional[str] = None


def _parse_tokens_header(tokens_str: Optional[str]) -> Optional[dict]:
    """Parse Google tokens from header"""
    if not tokens_str:
        return None
    try:
        return json.loads(tokens_str)
    except:
        return None


@router.get("/auth/status")
def google_auth_status_endpoint(
    x_google_tokens: Optional[str] = Header(None, alias="X-Google-Tokens")
):
    """
    Check Google Calendar connection status.
    Requires tokens in X-Google-Tokens header (JSON string).
    """
    tokens = _parse_tokens_header(x_google_tokens)
    return get_auth_status(tokens)


@router.post("/auth/status")
def google_auth_status_post(tokens: Optional[GoogleTokens] = None):
    """
    Check Google Calendar connection status.
    Accepts tokens in request body.
    """
    tokens_dict = tokens.model_dump() if tokens else None
    return get_auth_status(tokens_dict)


@router.get("/auth/url")
def google_auth_url_endpoint():
    """
    Get Google OAuth authorization URL.
    Returns URL and state for frontend to initiate OAuth flow.
    """
    result = get_auth_url()
    if not result:
        return JSONResponse(
            status_code=500,
            content={"error": "Google OAuth not configured. Check GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET."}
        )
    return result


@router.get("/auth/callback")
async def google_auth_callback(request: Request):
    """
    Handle Google OAuth callback.
    Exchanges code for tokens and redirects to the app via custom URL scheme.
    """
    try:
        code = request.query_params.get('code')
        state = request.query_params.get('state')
        
        if not code:
            # Redirect to app with error
            return HTMLResponse(
                content=_create_redirect_page("notioncapture://google-callback?error=no_code"),
                status_code=200
            )
        
        # Exchange code for tokens
        tokens = exchange_code_for_tokens(code, state or "")
        
        if not tokens:
            return HTMLResponse(
                content=_create_redirect_page("notioncapture://google-callback?error=token_exchange_failed"),
                status_code=200
            )
        
        # URL-encode the tokens JSON for the redirect
        import urllib.parse
        tokens_json = json.dumps(tokens)
        encoded_tokens = urllib.parse.quote(tokens_json)
        redirect_url = f"notioncapture://google-callback?tokens={encoded_tokens}"
        
        # Return HTML page that auto-redirects to the app
        return HTMLResponse(content=_create_redirect_page(redirect_url))
        
    except Exception as e:
        import urllib.parse
        error_msg = urllib.parse.quote(str(e))
        return HTMLResponse(
            content=_create_redirect_page(f"notioncapture://google-callback?error={error_msg}"),
            status_code=200
        )


def _create_redirect_page(redirect_url: str) -> str:
    """Create HTML page that redirects to the app via custom URL scheme"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Connecting...</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
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
        </style>
        <script>
            // Auto-redirect to app
            window.location.href = "{redirect_url}";
        </script>
    </head>
    <body>
        <div class="container">
            <div class="spinner"></div>
            <h1>Google Calendar Connected!</h1>
            <p>Redirecting to Notion Capture...</p>
            <div class="manual-link">
                <a href="{redirect_url}">Click here if not redirected automatically</a>
            </div>
        </div>
    </body>
    </html>
    """


@router.post("/auth/logout")
def google_auth_logout():
    """
    Logout from Google - Frontend should clear stored tokens.
    This endpoint just confirms the action.
    """
    return {"status": "success", "message": "Clear tokens on frontend to complete logout"}


@router.delete("/delete-event/{event_id}")
def delete_event_endpoint(
    event_id: str,
    x_google_tokens: Optional[str] = Header(None, alias="X-Google-Tokens")
):
    """Delete a Google Calendar event"""
    tokens = _parse_tokens_header(x_google_tokens)
    if not tokens:
        return JSONResponse(status_code=400, content={"error": "No Google tokens provided"})
    
    result = delete_calendar_event(tokens, event_id)
    if result.get("success"):
        return result
    else:
        return JSONResponse(status_code=500, content=result)


@router.post("/test-event")
def test_event_endpoint(
    x_google_tokens: Optional[str] = Header(None, alias="X-Google-Tokens")
):
    """Create a test calendar event"""
    tokens = _parse_tokens_header(x_google_tokens)
    if not tokens:
        return JSONResponse(status_code=400, content={"error": "No Google tokens provided"})
    
    local_now = datetime.now().astimezone()
    start = local_now.replace(hour=14, minute=0, second=0, microsecond=0)
    if local_now.hour >= 14:
        start += timedelta(days=1)
    
    test_entry = {
        "category": "event",
        "title": "Test Event from Notion Capture",
        "description": "This is a test event to verify calendar integration.",
        "start_time": start.isoformat(),
        "end_time": (start + timedelta(hours=1)).isoformat(),
    }
    
    result = create_calendar_event(tokens, test_entry)
    
    if result.get("success"):
        return {
            "status": "success",
            "message": "Test event created",
            **result
        }
    else:
        return JSONResponse(status_code=500, content=result)

