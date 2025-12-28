"""
Notion-related schemas
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel


class NotionAuthStatus(BaseModel):
    """Notion authentication status"""
    connected: bool
    workspace_name: Optional[str] = None
    selected_page_id: Optional[str] = None
    has_databases: bool = False
    error: Optional[str] = None
    setup_required: bool = False


class NotionPage(BaseModel):
    """Notion page"""
    id: str
    title: str
    icon: Optional[Dict[str, Any]] = None
    url: Optional[str] = None


class NotionDatabaseProperty(BaseModel):
    """Notion database property schema"""
    name: str
    type: str
    options: Optional[List[str]] = None
    config: Optional[Dict[str, Any]] = None


class NotionDatabase(BaseModel):
    """Notion database"""
    id: str
    title: str
    icon: Optional[Dict[str, Any]] = None
    url: Optional[str] = None
    properties: Dict[str, NotionDatabaseProperty] = {}
    property_count: int = 0

