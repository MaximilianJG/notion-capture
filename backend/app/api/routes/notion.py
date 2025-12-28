"""
Notion endpoints - Auth status and data operations
"""
from typing import Optional
from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.services.notion.client import get_auth_status
from app.services.notion.pages import fetch_pages
from app.services.notion.databases import fetch_databases, fetch_database_properties

router = APIRouter()


class NotionCredentials(BaseModel):
    """Notion credentials from frontend"""
    api_key: str
    selected_page_id: Optional[str] = None


@router.get("/auth/status")
def notion_auth_status_endpoint(
    x_notion_api_key: Optional[str] = Header(None, alias="X-Notion-Api-Key")
):
    """
    Check Notion connection status.
    Requires API key in X-Notion-Api-Key header.
    """
    return get_auth_status(x_notion_api_key)


@router.post("/auth/status")
def notion_auth_status_post(credentials: Optional[NotionCredentials] = None):
    """
    Check Notion connection status.
    Accepts API key in request body.
    """
    api_key = credentials.api_key if credentials else None
    return get_auth_status(api_key)


@router.get("/pages")
def get_notion_pages(
    x_notion_api_key: Optional[str] = Header(None, alias="X-Notion-Api-Key")
):
    """Get all accessible Notion pages"""
    if not x_notion_api_key:
        return JSONResponse(status_code=400, content={"error": "No Notion API key provided"})
    
    status = get_auth_status(x_notion_api_key)
    if not status.get("connected"):
        return JSONResponse(status_code=400, content={"error": "Notion not connected"})
    
    pages = fetch_pages(x_notion_api_key)
    return {"pages": pages, "count": len(pages)}


@router.get("/databases")
def get_notion_databases(
    page_id: Optional[str] = None,
    x_notion_api_key: Optional[str] = Header(None, alias="X-Notion-Api-Key"),
    x_notion_page_id: Optional[str] = Header(None, alias="X-Notion-Page-Id")
):
    """Get all databases, optionally filtered by parent page"""
    if not x_notion_api_key:
        return JSONResponse(status_code=400, content={"error": "No Notion API key provided"})
    
    status = get_auth_status(x_notion_api_key)
    if not status.get("connected"):
        return JSONResponse(status_code=400, content={"error": "Notion not connected"})
    
    filter_page_id = page_id or x_notion_page_id
    databases = fetch_databases(x_notion_api_key, filter_page_id)
    return {"databases": databases, "count": len(databases)}


@router.get("/databases/{database_id}/properties")
def get_database_properties_endpoint(
    database_id: str,
    x_notion_api_key: Optional[str] = Header(None, alias="X-Notion-Api-Key")
):
    """Get properties schema for a specific database"""
    if not x_notion_api_key:
        return JSONResponse(status_code=400, content={"error": "No Notion API key provided"})
    
    status = get_auth_status(x_notion_api_key)
    if not status.get("connected"):
        return JSONResponse(status_code=400, content={"error": "Notion not connected"})
    
    properties = fetch_database_properties(x_notion_api_key, database_id)
    return {"database_id": database_id, "properties": properties, "count": len(properties)}

