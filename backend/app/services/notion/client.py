"""
Notion API Client - Stateless, accepts API key per request
"""
import requests
from typing import Dict, Any, Optional, List
from datetime import datetime

NOTION_API_VERSION = "2022-06-28"
NOTION_API_BASE = "https://api.notion.com/v1"


class NotionClient:
    """Stateless Notion API client - requires API key for each operation"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Notion-Version": NOTION_API_VERSION,
            "Content-Type": "application/json"
        }
    
    def test_connection(self) -> Dict[str, Any]:
        """Test API key validity and get workspace info"""
        try:
            response = requests.get(
                f"{NOTION_API_BASE}/users/me",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                user_data = response.json()
                return {
                    "connected": True,
                    "workspace_name": user_data.get("name", "Notion"),
                    "type": user_data.get("type", "bot")
                }
            elif response.status_code == 401:
                return {
                    "connected": False,
                    "error": "Invalid API key"
                }
            else:
                return {
                    "connected": False,
                    "error": f"API error: {response.status_code}"
                }
        except Exception as e:
            return {
                "connected": False,
                "error": str(e)
            }
    
    def search(self, filter_obj: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Search Notion content"""
        try:
            response = requests.post(
                f"{NOTION_API_BASE}/search",
                headers=self.headers,
                json=filter_obj,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json().get("results", [])
            else:
                print(f"Notion search error: {response.text}")
                return []
        except Exception as e:
            print(f"Notion search exception: {e}")
            return []
    
    def get_database(self, database_id: str) -> Optional[Dict[str, Any]]:
        """Get database details"""
        try:
            response = requests.get(
                f"{NOTION_API_BASE}/databases/{database_id}",
                headers=self.headers,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Notion database error: {response.text}")
                return None
        except Exception as e:
            print(f"Notion database exception: {e}")
            return None
    
    def create_page(
        self,
        database_id: str,
        properties: Dict[str, Any],
        content_blocks: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """Create a new page in a database"""
        try:
            body = {
                "parent": {"database_id": database_id},
                "properties": properties
            }
            
            if content_blocks:
                body["children"] = content_blocks
            
            response = requests.post(
                f"{NOTION_API_BASE}/pages",
                headers=self.headers,
                json=body,
                timeout=30
            )
            
            if response.status_code in [200, 201]:
                page = response.json()
                print(f"Created Notion page: {page.get('id')}")
                return {
                    "success": True,
                    "page_id": page.get("id"),
                    "page_url": page.get("url")
                }
            else:
                error = response.json().get("message", response.text)
                print(f"Notion create page error: {error}")
                return {"success": False, "error": f"Notion API: {error}"}
                
        except Exception as e:
            print(f"Notion create page exception: {e}")
            return {"success": False, "error": str(e)}


def get_auth_status(api_key: Optional[str]) -> Dict[str, Any]:
    """Get Notion connection status for given API key"""
    if not api_key:
        return {
            "connected": False,
            "workspace_name": None,
            "error": "No Notion API key provided",
            "setup_required": True
        }
    
    client = NotionClient(api_key)
    result = client.test_connection()
    
    return {
        "connected": result.get("connected", False),
        "workspace_name": result.get("workspace_name"),
        "error": result.get("error"),
        "setup_required": not result.get("connected", False)
    }

