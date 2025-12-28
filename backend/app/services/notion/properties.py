"""
Notion Property value builders
"""
from typing import Dict, Any, Optional


def build_property_value(
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
                # Keep timezone offset if present
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


def apply_enriched_properties(
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
        
        prop_value = build_property_value(prop_type, value, prop_info)
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

