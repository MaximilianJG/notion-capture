"""
Capture-related schemas
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from .credentials import RequestCredentials


class TextInput(BaseModel):
    """Text input for capture"""
    text: str
    credentials: Optional[RequestCredentials] = None


class FilledProperty(BaseModel):
    """A property that was filled"""
    property: str
    value: str
    source: Optional[str] = None
    reasoning: Optional[str] = None
    type: Optional[str] = None


class EmptyProperty(BaseModel):
    """A property that was left empty"""
    property: str
    type: Optional[str] = None
    reason: Optional[str] = None


class CaptureResultSummary(BaseModel):
    """Summary of what happened during capture"""
    destination: Optional[str] = None
    database: Optional[str] = None
    filled_from_user: List[FilledProperty] = []
    filled_by_ai: List[FilledProperty] = []
    left_empty: List[EmptyProperty] = []
    assumptions: List[str] = []
    database_selection_reason: Optional[str] = None
    database_selection_confidence: Optional[float] = None
    mapping_reasoning: Optional[str] = None


class EventInfo(BaseModel):
    """Info about created calendar event"""
    title: str
    calendar_event_id: Optional[str] = None
    calendar_link: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    location: Optional[str] = None


class NotionInfo(BaseModel):
    """Info about created Notion page"""
    page_id: Optional[str] = None
    page_url: Optional[str] = None
    database: Optional[str] = None


class CaptureResult(BaseModel):
    """Full capture result"""
    status: str = "success"
    category: str
    title: str
    source_type: str
    ai_confidence: float = 0.0
    
    # Event-specific
    calendar_event_created: Optional[bool] = None
    event_info: Optional[EventInfo] = None
    calendar_error: Optional[str] = None
    
    # Notion-specific
    notion_created: Optional[bool] = None
    notion_info: Optional[NotionInfo] = None
    notion_error: Optional[str] = None
    
    # Summary
    summary: Optional[CaptureResultSummary] = None
    
    # Status
    google_status: Optional[Dict[str, Any]] = None
    notion_status: Optional[Dict[str, Any]] = None
    
    # Additional metadata
    input_type: Optional[str] = None
    input_length: Optional[int] = None
    filename: Optional[str] = None
    content_type: Optional[str] = None
    size_bytes: Optional[int] = None
    transcribed_text: Optional[str] = None

