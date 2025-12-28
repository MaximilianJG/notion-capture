"""
AI Property Mapper - Maps user data to Notion database properties
"""
import json
from typing import Dict, Any, Optional

from app.core import get_openai_client, get_local_datetime_context, log_ai_prompt, log_ai_response
from app.services.ai.prompts.loader import render_prompt


def _convert_to_notion_value(prop_type: str, value: Any, prop_info: Dict) -> Optional[Dict]:
    """Convert a value to Notion property format"""
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
            except:
                return None
        
        elif prop_type == "select":
            options = prop_info.get("options", [])
            str_val = str(value).strip()
            # Try exact match
            for opt in options:
                if opt.lower() == str_val.lower():
                    return {"select": {"name": opt}}
            # Use as-is (Notion creates new option)
            return {"select": {"name": str_val[:100]}}
        
        elif prop_type == "multi_select":
            if isinstance(value, list):
                tags = [{"name": str(t)[:100]} for t in value[:10]]
            else:
                tags = [{"name": str(value)[:100]}]
            return {"multi_select": tags}
        
        elif prop_type == "status":
            options = prop_info.get("options", [])
            str_val = str(value).strip()
            for opt in options:
                if opt.lower() == str_val.lower():
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
        print(f"Convert error for {prop_type}: {e}")
        return None


def map_properties_dynamically(
    user_data: Dict[str, Any],
    database_properties: Dict[str, Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Use AI to dynamically map user data to database properties.
    No hardcoded aliases - AI reasons about each property.
    """
    client = get_openai_client()
    if not client:
        return {
            "properties": {},
            "filled_from_user": [],
            "left_empty": list(database_properties.keys()),
            "ai_reasoning": "OpenAI not available"
        }
    
    dt_context = get_local_datetime_context()
    
    # Build property list with types and options
    props_info = []
    for prop_name, prop_data in database_properties.items():
        prop_type = prop_data.get("type", "unknown")
        # Skip auto-generated properties
        if prop_type in ["formula", "rollup", "created_time", "created_by", "last_edited_time", "last_edited_by"]:
            continue
        props_info.append({
            "name": prop_name,
            "type": prop_type,
            "options": prop_data.get("options", [])[:20] if prop_data.get("options") else None
        })
    
    raw_input = user_data.get("raw_input", user_data.get("source_text", ""))
    
    # Prepare user data for prompt (filter out internal fields)
    user_data_filtered = {
        k: v for k, v in user_data.items() 
        if k not in ['raw_response', 'success'] and v is not None
    }
    
    prompt = render_prompt(
        "map_properties",
        raw_input=raw_input,
        datetime_iso=dt_context['datetime_iso'],
        date=dt_context['date'],
        time=dt_context['time'],
        timezone=dt_context['timezone'],
        user_data_json=json.dumps(user_data_filtered, indent=2, default=str),
        properties_json=json.dumps(props_info, indent=2)
    )

    try:
        log_ai_prompt("map_properties_dynamically", prompt)
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000
        )
        
        ai_response = response.choices[0].message.content
        log_ai_response("map_properties_dynamically", ai_response)
        
        json_start = ai_response.find('{')
        json_end = ai_response.rfind('}') + 1
        
        if json_start >= 0 and json_end > json_start:
            result = json.loads(ai_response[json_start:json_end])
            
            mapped_properties = {}
            filled_from_user = []
            
            for mapping in result.get("mappings", []):
                prop_name = mapping.get("property")
                value = mapping.get("value")
                
                if prop_name and value is not None and prop_name in database_properties:
                    prop_info = database_properties[prop_name]
                    prop_type = prop_info.get("type", "rich_text")
                    
                    notion_value = _convert_to_notion_value(prop_type, value, prop_info)
                    if notion_value:
                        mapped_properties[prop_name] = notion_value
                        filled_from_user.append({
                            "property": prop_name,
                            "value": str(value)[:100],
                            "source": mapping.get("source", "ai"),
                            "reasoning": mapping.get("reasoning", ""),
                            "type": prop_type
                        })
            
            left_empty = [
                {"property": p, "type": database_properties[p].get("type", "unknown")}
                for p in result.get("unmapped_properties", [])
                if p in database_properties
            ]
            
            print(f"AI mapped {len(mapped_properties)} properties dynamically")
            
            return {
                "properties": mapped_properties,
                "filled_from_user": filled_from_user,
                "left_empty": left_empty,
                "ai_reasoning": result.get("overall_reasoning", "")
            }
        
        return {"properties": {}, "filled_from_user": [], "left_empty": [], "ai_reasoning": "Parse failed"}
        
    except Exception as e:
        print(f"AI Property Mapping Error: {e}")
        return {"properties": {}, "filled_from_user": [], "left_empty": [], "ai_reasoning": str(e)}
