"""
AI Enricher - Identifies researchable properties and enriches them
"""
import json
from typing import Dict, Any, List

from app.core import get_openai_client, get_local_datetime_context, log_ai_prompt, log_ai_response
from app.services.ai.prompts.loader import render_prompt


def identify_researchable_properties(
    user_data: Dict[str, Any],
    database_properties: Dict[str, Dict[str, Any]],
    empty_properties: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Use AI to dynamically identify which empty properties could be researched/filled.
    """
    client = get_openai_client()
    if not client or not empty_properties:
        return []
    
    raw_input = user_data.get("raw_input", user_data.get("source_text", ""))
    title = user_data.get("title", "")
    content_type = user_data.get("content_type", "")
    detailed_analysis = user_data.get("detailed_analysis", "")
    
    empty_props_info = []
    for prop in empty_properties:
        prop_name = prop.get("property", "")
        if prop_name in database_properties:
            prop_info = database_properties[prop_name]
            empty_props_info.append({
                "name": prop_name,
                "type": prop_info.get("type", "unknown"),
                "options": prop_info.get("options", [])[:15] if prop_info.get("options") else None
            })
    
    prompt = render_prompt(
        "identify_researchable",
        raw_input=raw_input,
        title=title,
        content_type=content_type,
        detailed_analysis=detailed_analysis,
        properties_json=json.dumps(empty_props_info, indent=2)
    )

    try:
        log_ai_prompt("identify_researchable_properties", prompt)
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000
        )
        
        ai_response = response.choices[0].message.content
        log_ai_response("identify_researchable_properties", ai_response)
        
        json_start = ai_response.find('{')
        json_end = ai_response.rfind('}') + 1
        
        if json_start >= 0 and json_end > json_start:
            result = json.loads(ai_response[json_start:json_end])
            researchable = result.get("researchable", [])
            print(f"AI identified {len(researchable)} researchable properties")
            return researchable
        
        return []
        
    except Exception as e:
        print(f"AI Researchable Identification Error: {e}")
        return []


def enrich_properties(
    user_data: Dict[str, Any],
    researchable_properties: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Use AI to research and fill researchable properties.
    """
    client = get_openai_client()
    if not client or not researchable_properties:
        return {}
    
    dt_context = get_local_datetime_context()
    
    raw_input = user_data.get("raw_input", user_data.get("source_text", ""))
    title = user_data.get("title", "")
    content_type = user_data.get("content_type", "")
    detailed_analysis = user_data.get("detailed_analysis", "")
    
    prompt = render_prompt(
        "enrich_properties",
        raw_input=raw_input,
        title=title,
        content_type=content_type,
        detailed_analysis=detailed_analysis,
        date=dt_context['date'],
        properties_json=json.dumps(researchable_properties, indent=2)
    )

    try:
        log_ai_prompt("enrich_properties", prompt)
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000
        )
        
        ai_response = response.choices[0].message.content
        log_ai_response("enrich_properties", ai_response)
        
        json_start = ai_response.find('{')
        json_end = ai_response.rfind('}') + 1
        
        if json_start >= 0 and json_end > json_start:
            enriched = json.loads(ai_response[json_start:json_end])
            result = {k: v for k, v in enriched.items() if v is not None}
            print(f"AI enriched {len(result)} properties")
            return result
        
        return {}
        
    except Exception as e:
        print(f"AI Enrichment Error: {e}")
        return {}
