"""
Capture Orchestration Service - Coordinates the full capture flow
Stateless - receives credentials per request
"""
from datetime import datetime
from typing import Dict, Any, Optional

from app.services import ai
from app.services.ai.analyzer import process_capture
from app.services.notion.client import NotionClient, get_auth_status as notion_auth_status
from app.services.notion.databases import fetch_databases, fetch_database_properties, detect_log_database, write_log_entry
from app.services.notion.properties import apply_enriched_properties
from app.services.google.auth import get_auth_status as google_auth_status
from app.services.google.calendar import create_calendar_event


def process_capture_result(
    analysis: Dict[str, Any],
    source_type: str,
    notion_api_key: Optional[str] = None,
    google_tokens: Optional[Dict[str, Any]] = None,
    selected_page_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Process AI analysis result and route to appropriate destination.
    Stateless - credentials passed per request.
    
    Returns full response with summary of what happened.
    """
    category = analysis.get("category", "other")
    title = analysis.get("title", "Untitled")
    
    result = {
        "status": "success",
        "category": category,
        "title": title,
        "source_type": source_type,
        "ai_confidence": analysis.get("ai_confidence", 0),
    }
    
    # Initialize summary
    summary = {
        "destination": None,
        "database": None,
        "filled_from_user": [],
        "filled_by_ai": [],
        "left_empty": [],
        "assumptions": []
    }
    
    if category == "event":
        # ==========================================
        # ROUTE TO GOOGLE CALENDAR
        # ==========================================
        print(f"📅 Routing to Google Calendar: {title}", flush=True)
        summary["destination"] = "Google Calendar"
        
        # Prepare event data
        event_data = {
            "category": "event",
            "title": title,
            "description": analysis.get("description"),
            "start_time": analysis.get("start_time"),
            "end_time": analysis.get("end_time"),
            "location": analysis.get("location"),
        }
        
        if not google_tokens:
            result["calendar_event_created"] = False
            result["calendar_error"] = "Google Calendar not connected. Please connect in settings."
        else:
            # Sync to Google Calendar
            sync_result = create_calendar_event(google_tokens, event_data)
            
            if sync_result.get("success"):
                result["calendar_event_created"] = True
                result["event_info"] = {
                    "title": title,
                    "calendar_event_id": sync_result.get("calendar_event_id"),
                    "calendar_link": sync_result.get("calendar_link"),
                    "start_time": analysis.get("start_time"),
                    "end_time": analysis.get("end_time"),
                    "location": analysis.get("location"),
                }
                
                summary["filled_from_user"] = [
                    {"field": "title", "value": title},
                    {"field": "start_time", "value": analysis.get("start_time")},
                ]
                if analysis.get("end_time"):
                    summary["filled_from_user"].append({"field": "end_time", "value": analysis.get("end_time")})
                if analysis.get("location"):
                    summary["filled_from_user"].append({"field": "location", "value": analysis.get("location")})
                
                print(f"✅ Event created in Google Calendar", flush=True)
            else:
                result["calendar_event_created"] = False
                result["calendar_error"] = sync_result.get("error", "Unknown error")
                print(f"❌ Failed to create event: {sync_result.get('error')}", flush=True)
    
    else:
        # ==========================================
        # ROUTE TO NOTION
        # ==========================================
        print(f"📓 Routing to Notion: {title}", flush=True)
        summary["destination"] = "Notion"
        
        # Check Notion connection
        if not notion_api_key:
            result["notion_created"] = False
            result["notion_error"] = "Notion not connected. Please add your API key in settings."
            summary["left_empty"].append({"reason": "Notion not connected"})
        else:
            # Get databases
            databases = fetch_databases(notion_api_key, selected_page_id)
            
            if not databases:
                result["notion_created"] = False
                result["notion_error"] = "No Notion databases found. Please share databases with your integration."
            else:
                # Select best database using AI
                db_selection = ai.select_best_database(analysis, databases)
                
                # Get log database early for writing failures too
                log_db_id = detect_log_database(databases)
                
                if not db_selection.get("success"):
                    # AI couldn't find a fitting database
                    result["notion_created"] = False
                    result["notion_error"] = f"No suitable database found: {db_selection.get('reason', 'Unknown reason')}"
                    summary["database_selection_failed"] = True
                    summary["database_selection_reason"] = db_selection.get("reason", "Unknown")
                    
                    # Detailed log entry
                    db_names = [db.get("title", "Untitled") for db in databases]
                    failure_details = (
                        f"FAILURE: No suitable database. "
                        f"Raw input: '{analysis.get('raw_input', '')}'. "
                        f"Available DBs: {', '.join(db_names)}. "
                        f"Reason: {db_selection.get('reason', 'Unknown')}"
                    )
                    
                    # Write failure to Notion log database
                    if log_db_id:
                        log_data = {
                            "action": f"FAILED: {title}",
                            "timestamp": datetime.now().astimezone().isoformat(),
                            "result": "Failed",
                            "database": "None (no match)",
                            "details": failure_details
                        }
                        write_log_entry(notion_api_key, log_db_id, log_data)
                        print(f"📝 Failure logged to Notion", flush=True)
                    
                    print(f"❌ Database selection failed: {db_selection.get('reason')}", flush=True)
                else:
                    selected_db = db_selection["database"]
                    db_id = selected_db["id"]
                    db_title = selected_db.get("title", "Unknown")
                    summary["database"] = db_title
                    summary["database_selection_reason"] = db_selection.get("reason", "")
                    summary["database_selection_confidence"] = db_selection.get("confidence", 0.0)
                    
                    print(f"📚 Selected database: {db_title} (confidence: {db_selection.get('confidence', 0):.2f})", flush=True)
                    
                    # Fetch database properties
                    properties = fetch_database_properties(notion_api_key, db_id)
                    
                    # DYNAMIC AI PROPERTY MAPPING
                    print(f"🤖 AI mapping properties dynamically...", flush=True)
                    mapping_result = ai.map_properties_dynamically(analysis, properties)
                    mapped_properties = mapping_result["properties"]
                    summary["filled_from_user"] = mapping_result["filled_from_user"]
                    summary["left_empty"] = mapping_result["left_empty"]
                    summary["mapping_reasoning"] = mapping_result.get("ai_reasoning", "")
                    
                    print(f"📝 Mapped {len(mapped_properties)} properties", flush=True)
                    
                    # DYNAMIC AI RESEARCHABLE IDENTIFICATION
                    if mapping_result["left_empty"]:
                        print(f"🔍 AI identifying researchable properties...", flush=True)
                        researchable = ai.identify_researchable_properties(
                            analysis, properties, mapping_result["left_empty"]
                        )
                        
                        # AI enrichment for researchable properties
                        if researchable:
                            print(f"🔬 Enriching {len(researchable)} researchable properties with AI...", flush=True)
                            enriched_data = ai.enrich_properties(analysis, researchable)
                            
                            if enriched_data:
                                enrich_result = apply_enriched_properties(
                                    mapped_properties,
                                    enriched_data,
                                    properties
                                )
                                mapped_properties = enrich_result["properties"]
                                summary["filled_by_ai"] = enrich_result["filled_by_ai"]
                                
                                # Update left_empty to remove AI-filled properties
                                ai_filled_names = [p["property"] for p in summary["filled_by_ai"]]
                                summary["left_empty"] = [
                                    p for p in summary["left_empty"]
                                    if p.get("property") not in ai_filled_names
                                ]
                    
                    # Create Notion page
                    client = NotionClient(notion_api_key)
                    create_result = client.create_page(db_id, mapped_properties)
                    
                    if create_result.get("success"):
                        result["notion_created"] = True
                        result["notion_info"] = {
                            "page_id": create_result.get("page_id"),
                            "page_url": create_result.get("page_url"),
                            "database": db_title
                        }
                        
                        # Build detailed log description
                        filled_props = [f"{p['property']}={p.get('value', '')[:30]}" for p in summary.get("filled_from_user", [])]
                        ai_props = [f"{p['property']}={p['value']}" for p in summary.get("filled_by_ai", [])]
                        log_details = (
                            f"SUCCESS. Raw input: '{analysis.get('raw_input', '')}'. "
                            f"Database: {db_title}. "
                            f"Mapped: {', '.join(filled_props) if filled_props else 'None'}. "
                            f"AI-researched: {', '.join(ai_props) if ai_props else 'None'}."
                        )
                        
                        print(f"✅ Page created in Notion database: {db_title}", flush=True)
                        
                        # Write to log database if exists
                        if log_db_id:
                            log_data = {
                                "action": f"Created: {title}",
                                "timestamp": datetime.now().astimezone().isoformat(),
                                "result": "Success",
                                "database": db_title,
                                "details": log_details
                            }
                            write_log_entry(notion_api_key, log_db_id, log_data)
                            print(f"📝 Log entry written to Notion", flush=True)
                    else:
                        result["notion_created"] = False
                        result["notion_error"] = create_result.get("error", "Unknown error")
                        
                        failure_details = (
                            f"FAILURE: Page creation error. "
                            f"Raw input: '{analysis.get('raw_input', '')}'. "
                            f"Database: {db_title}. "
                            f"Error: {create_result.get('error', '')}"
                        )
                        
                        # Write failure to Notion log database
                        if log_db_id:
                            log_data = {
                                "action": f"FAILED: {title}",
                                "timestamp": datetime.now().astimezone().isoformat(),
                                "result": "Failed",
                                "database": db_title,
                                "details": failure_details
                            }
                            write_log_entry(notion_api_key, log_db_id, log_data)
                            print(f"📝 Failure logged to Notion", flush=True)
                        
                        print(f"❌ Failed to create Notion page: {create_result.get('error')}", flush=True)
    
    # Add summary and auth status to result
    result["summary"] = summary
    result["google_status"] = google_auth_status(google_tokens)
    result["notion_status"] = notion_auth_status(notion_api_key)
    
    return result

