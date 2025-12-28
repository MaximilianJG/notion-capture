"""
Notion Services - Stateless API operations
All methods accept API key as parameter - no stored credentials
"""
from .client import NotionClient
from .pages import fetch_pages
from .databases import fetch_databases, fetch_database_properties, detect_log_database
from .properties import build_property_value, apply_enriched_properties

__all__ = [
    "NotionClient",
    "fetch_pages",
    "fetch_databases", 
    "fetch_database_properties",
    "detect_log_database",
    "build_property_value",
    "apply_enriched_properties",
]

