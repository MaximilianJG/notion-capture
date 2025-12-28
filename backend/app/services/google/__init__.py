"""
Google Services - Stateless OAuth and Calendar operations
All methods accept credentials as parameter - no stored tokens
"""
from .auth import (
    get_auth_url,
    exchange_code_for_tokens,
    refresh_access_token,
    get_auth_status,
    build_credentials_from_tokens
)
from .calendar import create_calendar_event, delete_calendar_event

__all__ = [
    "get_auth_url",
    "exchange_code_for_tokens",
    "refresh_access_token",
    "get_auth_status",
    "build_credentials_from_tokens",
    "create_calendar_event",
    "delete_calendar_event",
]

