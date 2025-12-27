"""
Notion Service - Handles Notion API operations using Internal Integration
Uses a simple API token (NOTION_API_KEY) - no OAuth required.
"""
import os
import json
import requests
from datetime import datetime
from typing import Dict, Any, Optional, List


# Configuration
NOTION_API_VERSION = "2022-06-28"
NOTION_API_KEY = os.getenv("NOTION_API_KEY", "")


class NotionService:
    """Service for all Notion operations using Internal Integration"""
    
    _instance = None
    _selected_page_id: Optional[str] = None
    _databases_cache: Dict[str, Dict[str, Any]] = {}
    _workspace_info: Optional[Dict[str, Any]] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_settings()
        return cls._instance
    
    def _load_settings(self):
        """Load saved settings"""
        settings_file = "notion_settings.json"
        if os.path.exists(settings_file):
            try:
                with open(settings_file, 'r') as f:
                    data = json.load(f)
                    self._selected_page_id = data.get("selected_page_id")
                    print(f"Loaded Notion settings")
            except Exception as e:
                print(f"Error loading Notion settings: {e}")
    
    def _save_settings(self):
        """Save settings for persistence"""
        settings_file = "notion_settings.json"
        try:
            with open(settings_file, 'w') as f:
                json.dump({"selected_page_id": self._selected_page_id}, f)
        except Exception as e:
            print(f"Error saving Notion settings: {e}")
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for Notion API requests"""
        return {
            "Authorization": f"Bearer {NOTION_API_KEY}",
            "Notion-Version": NOTION_API_VERSION,
            "Content-Type": "application/json"
        }
    
    def _get_api_key(self) -> str:
        """Get the current API key"""
        global NOTION_API_KEY
        NOTION_API_KEY = os.getenv("NOTION_API_KEY", "")
        return NOTION_API_KEY
    
    # ==================== Connection Status ====================
    
    def get_auth_status(self) -> Dict[str, Any]:
        """Get current Notion connection status"""
        api_key = self._get_api_key()
        
        if not api_key:
            return {
                "connected": False,
                "workspace_name": None,
                "error": "NOTION_API_KEY not set in environment",
                "setup_required": True
            }
        
        if self._workspace_info is None:
            try:
                response = requests.get(
                    "https://api.notion.com/v1/users/me",
                    headers=self._get_headers(),
                    timeout=10
                )
                
                if response.status_code == 200:
                    user_data = response.json()
                    self._workspace_info = {
                        "name": user_data.get("name", "Notion"),
                        "type": user_data.get("type", "bot")
                    }
                elif response.status_code == 401:
                    return {
                        "connected": False,
                        "workspace_name": None,
                        "error": "Invalid API key",
                        "setup_required": True
                    }
                else:
                    return {
                        "connected": False,
                        "workspace_name": None,
                        "error": f"API error: {response.status_code}",
                        "setup_required": False
                    }
            except Exception as e:
                return {
                    "connected": False,
                    "workspace_name": None,
                    "error": str(e),
                    "setup_required": False
                }
        
        return {
            "connected": True,
            "workspace_name": self._workspace_info.get("name", "Notion"),
            "selected_page_id": self._selected_page_id,
            "has_databases": len(self._databases_cache) > 0,
            "setup_required": False
        }
    
    def set_selected_page(self, page_id: str):
        """Set the selected page for database operations"""
        self._selected_page_id = page_id
        self._save_settings()
        print(f"Selected Notion page: {page_id}")
    
    def get_selected_page_id(self) -> Optional[str]:
        """Get the currently selected page ID"""
        return self._selected_page_id
    
    # ==================== Pages ====================
    
    def fetch_pages(self) -> List[Dict[str, Any]]:
        """Fetch all accessible pages from Notion"""
        if not self._get_api_key():
            return []
        
        try:
            response = requests.post(
                "https://api.notion.com/v1/search",
                headers=self._get_headers(),
                json={"filter": {"property": "object", "value": "page"}},
                timeout=30
            )
            
            if response.status_code != 200:
                print(f"Notion search error: {response.text}")
                return []
            
            pages = []
            for page in response.json().get("results", []):
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
            
        except Exception as e:
            print(f"Error fetching pages: {e}")
            return []
    
    # ==================== Databases ====================
    
    def fetch_databases_in_page(self, page_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch all databases the integration has access to"""
        if not self._get_api_key():
            return []
        
        try:
            response = requests.post(
                "https://api.notion.com/v1/search",
                headers=self._get_headers(),
                json={"filter": {"property": "object", "value": "database"}},
                timeout=30
            )
            
            if response.status_code != 200:
                print(f"Notion search error: {response.text}")
                return []
            
            databases = []
            for db in response.json().get("results", []):
                db_id = db["id"]
                
                if page_id:
                    parent = db.get("parent", {})
                    parent_id = parent.get("page_id") or parent.get("workspace")
                    if parent_id != page_id and parent.get("type") != "workspace":
                        continue
                
                title_parts = db.get("title", [])
                title = title_parts[0].get("text", {}).get("content", "Untitled") if title_parts else "Untitled"
                
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
                self._databases_cache[db_id] = db_info
            
            print(f"Found {len(databases)} Notion databases")
            return databases
            
        except Exception as e:
            print(f"Error fetching databases: {e}")
            return []
    
    def fetch_database_properties(self, database_id: str) -> Dict[str, Dict[str, Any]]:
        """Fetch detailed properties schema for a database"""
        if not self._get_api_key():
            return {}
        
        try:
            response = requests.get(
                f"https://api.notion.com/v1/databases/{database_id}",
                headers=self._get_headers(),
                timeout=30
            )
            
            if response.status_code != 200:
                print(f"Notion database error: {response.text}")
                return {}
            
            db = response.json()
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
            
            if database_id in self._databases_cache:
                self._databases_cache[database_id]["properties"] = properties
            
            return properties
            
        except Exception as e:
            print(f"Error fetching database properties: {e}")
            return {}
    
    # ==================== Apply AI-Enriched Properties ====================
    
    def apply_enriched_properties(
        self, 
        existing_properties: Dict[str, Any],
        enriched_data: Dict[str, Any],
        properties_schema: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Apply AI-enriched data to existing property mappings."""
        result = existing_properties.copy()
        filled_by_ai = []
        
        for prop_name, value in enriched_data.items():
            if value is None:
                continue
            
            prop_info = properties_schema.get(prop_name, {})
            prop_type = prop_info.get("type", "rich_text")
            
            prop_value = self._build_property_value(prop_type, value, prop_info)
            if prop_value:
                result[prop_name] = prop_value
                filled_by_ai.append({
                    "property": prop_name,
                    "value": str(value)[:100],
                    "type": prop_type
                })
        
        return {
            "properties": result,
            "filled_by_ai": filled_by_ai
        }
    
    def _build_property_value(
        self, 
        prop_type: str, 
        value: Any, 
        prop_info: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Build a Notion property value based on its type"""
        if value is None:
            return None
        
        try:
            if prop_type == "title":
                return {"title": [{"text": {"content": str(value)[:2000]}}]}
            
            elif prop_type == "rich_text":
                return {"rich_text": [{"text": {"content": str(value)[:2000]}}]}
            
            elif prop_type == "number":
                try:
                    return {"number": float(value)}
                except (ValueError, TypeError):
                    return None
            
            elif prop_type == "select":
                options = prop_info.get("options", [])
                str_value = str(value).strip()
                for opt in options:
                    if opt.lower() == str_value.lower():
                        return {"select": {"name": opt}}
                return {"select": {"name": str_value[:100]}}
            
            elif prop_type == "multi_select":
                if isinstance(value, list):
                    tags = [{"name": str(t)[:100]} for t in value[:10]]
                else:
                    tags = [{"name": str(value)[:100]}]
                return {"multi_select": tags}
            
            elif prop_type == "status":
                options = prop_info.get("options", [])
                str_value = str(value).strip()
                for opt in options:
                    if opt.lower() == str_value.lower():
                        return {"status": {"name": opt}}
                if options:
                    return {"status": {"name": options[0]}}
                return None
            
            elif prop_type == "date":
                date_str = str(value)
                if 'T' in date_str:
                    # Keep timezone offset if present (format: 2024-01-15T10:30:00+01:00)
                    # Notion accepts ISO 8601 with timezone
                    if '+' in date_str or date_str.endswith('Z'):
                        return {"date": {"start": date_str}}
                    else:
                        return {"date": {"start": date_str[:19]}}
                else:
                    return {"date": {"start": date_str[:10]}}
            
            elif prop_type == "checkbox":
                if isinstance(value, bool):
                    return {"checkbox": value}
                return {"checkbox": str(value).lower() in ['true', 'yes', '1']}
            
            elif prop_type == "url":
                return {"url": str(value)}
            
            elif prop_type == "email":
                return {"email": str(value)}
            
            elif prop_type == "phone_number":
                return {"phone_number": str(value)}
            
            return None
            
        except Exception as e:
            print(f"Error building property {prop_type}: {e}")
            return None
    
    # ==================== Create Page ====================
    
    def create_page(
        self, 
        database_id: str, 
        properties: Dict[str, Any],
        content_blocks: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """Create a new page in a Notion database"""
        if not self._get_api_key():
            return {"success": False, "error": "Notion not connected (NOTION_API_KEY not set)"}
        
        try:
            body = {
                "parent": {"database_id": database_id},
                "properties": properties
            }
            
            if content_blocks:
                body["children"] = content_blocks
            
            response = requests.post(
                "https://api.notion.com/v1/pages",
                headers=self._get_headers(),
                json=body,
                timeout=30
            )
            
            if response.status_code not in [200, 201]:
                error = response.json().get("message", response.text)
                print(f"Notion create page error: {error}")
                return {"success": False, "error": f"Notion API: {error}"}
            
            page = response.json()
            print(f"Created Notion page: {page.get('id')}")
            
            return {
                "success": True,
                "page_id": page.get("id"),
                "page_url": page.get("url")
            }
            
        except Exception as e:
            print(f"Error creating Notion page: {e}")
            return {"success": False, "error": str(e)}
    
    # ==================== Log Database ====================
    
    def detect_log_database(self, databases: Optional[List[Dict[str, Any]]] = None) -> Optional[str]:
        """Detect if a log database exists by name matching."""
        if databases is None:
            databases = list(self._databases_cache.values())
        
        log_indicators = ["log", "logs", "activity", "history", "journal"]
        
        for db in databases:
            title = db.get("title", "").lower()
            for indicator in log_indicators:
                if indicator in title:
                    return db.get("id")
        
        return None
    
    def write_log_entry(
        self, 
        log_database_id: str, 
        log_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Write a log entry to the log database"""
        if not self._get_api_key():
            return {"success": False, "error": "Notion not connected"}
        
        properties = self.fetch_database_properties(log_database_id)
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
                    # Use full ISO format with timezone
                    timestamp = log_data.get("timestamp") or datetime.now().astimezone().isoformat()
                    log_properties[prop_name] = {
                        "date": {"start": timestamp}
                    }
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
        
        return self.create_page(log_database_id, log_properties)


# Singleton instance
notion_service = NotionService()
