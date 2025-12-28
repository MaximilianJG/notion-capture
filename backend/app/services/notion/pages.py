"""
Notion Pages operations
"""
from typing import List, Dict, Any

from .client import NotionClient


def fetch_pages(api_key: str) -> List[Dict[str, Any]]:
    """Fetch all accessible pages from Notion"""
    client = NotionClient(api_key)
    
    results = client.search({"filter": {"property": "object", "value": "page"}})
    
    pages = []
    for page in results:
        page_id = page["id"]
        title = "Untitled"
        properties = page.get("properties", {})
        
        if "title" in properties:
            title_parts = properties["title"].get("title", [])
            if title_parts:
                title = title_parts[0].get("text", {}).get("content", "Untitled")
        elif "Name" in properties:
            title_parts = properties["Name"].get("title", [])
            if title_parts:
                title = title_parts[0].get("text", {}).get("content", "Untitled")
        
        pages.append({
            "id": page_id,
            "title": title,
            "icon": page.get("icon"),
            "url": page.get("url")
        })
    
    print(f"Found {len(pages)} Notion pages")
    return pages

