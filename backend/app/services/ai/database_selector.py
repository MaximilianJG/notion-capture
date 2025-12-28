"""
AI Database Selector - Selects best Notion database for content
"""
import json
from typing import Dict, Any, List

from app.core import get_openai_client, log_ai_prompt, log_ai_response
from app.services.ai.prompts.loader import render_prompt


def select_best_database(
    user_data: Dict[str, Any],
    databases: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Use AI to select the most appropriate database.
    Returns detailed result with success/failure and reasoning.
    """
    client = get_openai_client()
    
    if not databases:
        return {
            "success": False,
            "database": None,
            "reason": "No databases available. Please share a Notion page with databases.",
            "confidence": 0.0
        }
    
    if not client:
        return {
            "success": True,
            "database": databases[0],
            "reason": "OpenAI not configured - using first database",
            "confidence": 0.3
        }
    
    raw_input = user_data.get("raw_input", user_data.get("source_text", ""))
    title = user_data.get("title", "")
    description = user_data.get("description", "")
    content_type = user_data.get("content_type", "")
    detailed_analysis = user_data.get("detailed_analysis", "")
    
    db_list = []
    for i, db in enumerate(databases):
        db_list.append({
            "index": i,
            "title": db.get("title", "Untitled"),
            "properties": list(db.get("properties", {}).keys())[:15]
        })
    
    prompt = render_prompt(
        "select_database",
        raw_input=raw_input,
        title=title,
        description=description,
        content_type=content_type,
        detailed_analysis=detailed_analysis,
        databases_json=json.dumps(db_list, indent=2)
    )

    try:
        log_ai_prompt("select_best_database", prompt)
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400
        )
        
        ai_response = response.choices[0].message.content
        log_ai_response("select_best_database", ai_response)
        
        json_start = ai_response.find('{')
        json_end = ai_response.rfind('}') + 1
        
        if json_start >= 0 and json_end > json_start:
            result = json.loads(ai_response[json_start:json_end])
            found_match = result.get("found_match", False)
            index = result.get("selected_index")
            confidence = float(result.get("confidence", 0.0))
            reason = result.get("reason", "No reason provided")
            
            if found_match and index is not None and 0 <= index < len(databases) and confidence >= 0.5:
                print(f"AI selected database: {databases[index].get('title')} (confidence: {confidence:.2f})")
                return {
                    "success": True,
                    "database": databases[index],
                    "reason": reason,
                    "confidence": confidence
                }
            else:
                print(f"AI could not find fitting database: {reason}")
                return {
                    "success": False,
                    "database": None,
                    "reason": reason,
                    "confidence": confidence
                }
        
        return {"success": False, "database": None, "reason": "Parse failed", "confidence": 0.0}
        
    except Exception as e:
        print(f"AI Database Selection Error: {e}")
        return {"success": False, "database": None, "reason": str(e), "confidence": 0.0}
