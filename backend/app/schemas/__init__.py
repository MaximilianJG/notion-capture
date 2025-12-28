"""Pydantic schemas for API models"""
from .capture import TextInput, CaptureResult, CaptureResultSummary
from .google import GoogleAuthStatus, GoogleCredentials, GoogleAuthURL
from .notion import NotionAuthStatus, NotionPage, NotionDatabase, NotionDatabaseProperty
from .credentials import RequestCredentials

__all__ = [
    # Capture
    "TextInput",
    "CaptureResult", 
    "CaptureResultSummary",
    # Google
    "GoogleAuthStatus",
    "GoogleCredentials",
    "GoogleAuthURL",
    # Notion
    "NotionAuthStatus",
    "NotionPage",
    "NotionDatabase",
    "NotionDatabaseProperty",
    # Credentials
    "RequestCredentials",
]

