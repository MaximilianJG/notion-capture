"""
Notion Database operations
"""
from typing import List, Dict, Any, Optional

from .client import NotionClient


def fetch_databases(api_key: str, page_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetch all databases the integration has access to"""
    client = NotionClient(api_key)
    
    results = client.search({"filter": {"property": "object", "value": "database"}})
    
    databases = []
    for db in results:
        db_id = db["id"]
        
        # Optional filter by parent page
        if page_id:
            parent = db.get("parent", {})
            parent_id = parent.get("page_id") or parent.get("workspace")
            if parent_id != page_id and parent.get("type") != "workspace":
                continue
        
        title_parts = db.get("title", [])
        title = title_parts[0].get("text", {}).get("content", "Untitled") if title_parts else "Untitled"
        
        # Extract properties schema
        properties = {}
        for prop_name, prop_data in db.get("properties", {}).items():
            properties[prop_name] = {
                "name": prop_name,
                "type": prop_data.get("type"),
                "config": prop_data
            }
        
        db_info = {
            "id": db_id,
            "title": title,
            "icon": db.get("icon"),
            "url": db.get("url"),
            "properties": properties,
            "property_count": len(properties)
        }
        
        databases.append(db_info)
    
    print(f"Found {len(databases)} Notion databases")
    return databases


def fetch_database_properties(api_key: str, database_id: str) -> Dict[str, Dict[str, Any]]:
    """Fetch detailed properties schema for a database"""
    client = NotionClient(api_key)
    
    db = client.get_database(database_id)
    if not db:
        return {}
    
    properties = {}
    for prop_name, prop_data in db.get("properties", {}).items():
        prop_type = prop_data.get("type")
        options = []
        
        if prop_type == "select" and "select" in prop_data:
            options = [opt.get("name") for opt in prop_data["select"].get("options", [])]
        elif prop_type == "multi_select" and "multi_select" in prop_data:
            options = [opt.get("name") for opt in prop_data["multi_select"].get("options", [])]
        elif prop_type == "status" and "status" in prop_data:
            options = [opt.get("name") for opt in prop_data["status"].get("options", [])]
        
        properties[prop_name] = {
            "name": prop_name,
            "type": prop_type,
            "options": options,
            "config": prop_data
        }
    
    return properties


def detect_log_database(databases: List[Dict[str, Any]]) -> Optional[str]:
    """Detect if a log database exists by name matching."""
    log_indicators = ["log", "logs", "activity", "history", "journal"]
    
    for db in databases:
        title = db.get("title", "").lower()
        for indicator in log_indicators:
            if indicator in title:
                return db.get("id")
    
    return None


def write_log_entry(
    api_key: str,
    log_database_id: str,
    log_data: Dict[str, Any]
) -> Dict[str, Any]:
    """Write a log entry to the log database"""
    from datetime import datetime
    from .properties import build_property_value
    
    client = NotionClient(api_key)
    properties = fetch_database_properties(api_key, log_database_id)
    
    log_properties = {}
    
    for prop_name, prop_info in properties.items():
        prop_type = prop_info["type"]
        prop_name_lower = prop_name.lower()
        
        if prop_type == "title":
            log_properties[prop_name] = {
                "title": [{"text": {"content": log_data.get("action", "Capture")[:2000]}}]
            }
        elif "time" in prop_name_lower or "date" in prop_name_lower:
            if prop_type == "date":
                timestamp = log_data.get("timestamp") or datetime.now().astimezone().isoformat()
                log_properties[prop_name] = {"date": {"start": timestamp}}
        elif "result" in prop_name_lower or "status" in prop_name_lower:
            if prop_type == "select":
                log_properties[prop_name] = {"select": {"name": log_data.get("result", "Success")}}
            elif prop_type == "rich_text":
                log_properties[prop_name] = {"rich_text": [{"text": {"content": log_data.get("result", "Success")}}]}
        elif "detail" in prop_name_lower or "description" in prop_name_lower or "note" in prop_name_lower:
            if prop_type == "rich_text":
                log_properties[prop_name] = {"rich_text": [{"text": {"content": log_data.get("details", "")[:2000]}}]}
        elif "database" in prop_name_lower or "target" in prop_name_lower:
            if prop_type == "rich_text":
                log_properties[prop_name] = {"rich_text": [{"text": {"content": log_data.get("database", "")}}]}
            elif prop_type == "select":
                log_properties[prop_name] = {"select": {"name": log_data.get("database", "Unknown")}}
    
    return client.create_page(log_database_id, log_properties)

