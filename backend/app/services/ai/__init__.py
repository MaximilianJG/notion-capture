"""
AI Services - Facade for all AI operations
"""
from .analyzer import analyze_text, analyze_screenshot, extract_text_ocr
from .database_selector import select_best_database
from .property_mapper import map_properties_dynamically
from .enricher import identify_researchable_properties, enrich_properties

__all__ = [
    "analyze_text",
    "analyze_screenshot", 
    "extract_text_ocr",
    "select_best_database",
    "map_properties_dynamically",
    "identify_researchable_properties",
    "enrich_properties",
]


# Categories
CATEGORIES = {
    "event": "Calendar events with date, time, location",
    "other": "Everything else - goes to Notion"
}


def get_categories():
    return CATEGORIES


def get_category_names():
    return list(CATEGORIES.keys())

