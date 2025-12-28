"""
Notion Capture API - Slim Single-Purpose Flow

Architecture:
1. AI Layer (services/ai.py) - OCR + GPT-4o analysis, determines event vs other
2. External Layer (services/external.py) - Google Calendar OAuth and event creation
3. Notion Layer (services/notion.py) - Notion OAuth, database operations

Flow: Capture → AI Analysis → Route to Google Calendar (events) OR Notion (everything else)
"""
import os
import sys
import ssl
import warnings
from datetime import datetime
from typing import Dict, Any, List, Optional

# Fix SSL certificate issues on macOS - disable verification for development
ssl._create_default_https_context = ssl._create_unverified_context
os.environ['PYTHONHTTPSVERIFY'] = '0'

# Suppress SSL warnings in development
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings('ignore', message='Unverified HTTPS request')

# Also try certifi if available
try:
    import certifi
    os.environ['SSL_CERT_FILE'] = certifi.where()
    os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
except ImportError:
    pass

# Monkey-patch httpx to disable SSL verification
import httpx
_original_client_init = httpx.Client.__init__
def _patched_client_init(self, *args, **kwargs):
    kwargs['verify'] = False
    _original_client_init(self, *args, **kwargs)
httpx.Client.__init__ = _patched_client_init

_original_async_client_init = httpx.AsyncClient.__init__
def _patched_async_client_init(self, *args, **kwargs):
    kwargs['verify'] = False
    _original_async_client_init(self, *args, **kwargs)
httpx.AsyncClient.__init__ = _patched_async_client_init

from fastapi import FastAPI, File, UploadFile, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Force unbuffered output
print("🔧 Starting server initialization...", flush=True)

# Load environment variables
print("🔧 Loading environment variables...", flush=True)
from dotenv import load_dotenv
load_dotenv()
print("✅ Environment variables loaded", flush=True)

# Import services
from services.ai import ai_service
from services.external import external_service
from services.notion import notion_service

print("🔧 Creating FastAPI app...", flush=True)
app = FastAPI(title="Notion Capture API", version="3.0.0")
print("✅ FastAPI app created", flush=True)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================
# IN-MEMORY SESSION LOG
# ============================================
session_log: List[Dict[str, Any]] = []

def add_log_entry(action: str, result: str, details: str = "", target: str = ""):
    """Add an entry to the in-memory session log"""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "action": action,
        "result": result,
        "details": details,
        "target": target
    }
    session_log.append(entry)
    # Keep only last 100 entries
    if len(session_log) > 100:
        session_log.pop(0)
    return entry


# ============================================
# ROOT & HEALTH ENDPOINTS
# ============================================

@app.get("/")
def root():
    """Root endpoint - API information"""
    return {
        "name": "Notion Capture API",
        "version": "3.0.0",
        "description": "Slim single-purpose capture flow: Events → Google Calendar, Everything else → Notion",
        "architecture": {
            "ai": "GPT-4o Vision + OCR",
            "calendar": "Google Calendar",
            "storage": "Notion"
        },
        "endpoints": {
            "health": "/health",
            "capture": "/upload-screenshot, /process-text",
            "google": "/google/auth/*",
            "notion": "/notion/*",
            "logs": "/logs"
        }
    }

@app.get("/health")
def health():
    return {"ok": True}

@app.on_event("startup")
async def startup_event():
    print("🚀 FastAPI server started!", flush=True)
    print("🌐 API available at http://127.0.0.1:8000", flush=True)
    print("📚 API docs available at http://127.0.0.1:8000/docs", flush=True)


# ============================================
# MAIN CAPTURE ENDPOINTS
# ============================================

class TextInput(BaseModel):
    text: str


def process_capture_result(analysis: Dict[str, Any], source_type: str) -> Dict[str, Any]:
    """
    Process AI analysis result and route to appropriate destination.
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
        
        # Sync to Google Calendar
        sync_result = external_service.sync_to_google_calendar(event_data)
        
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
            
            # Build detailed log description
            event_details = (
                f"Raw input: '{analysis.get('raw_input', '')[:60]}'. "
                f"Event: {title}. "
                f"Start: {analysis.get('start_time', 'N/A')}. "
                f"Location: {analysis.get('location', 'N/A')}."
            )
            add_log_entry("Create Event", "Success", event_details, "Google Calendar")
            print(f"✅ Event created in Google Calendar", flush=True)
        else:
            result["calendar_event_created"] = False
            result["calendar_error"] = sync_result.get("error", "Unknown error")
            add_log_entry(
                "Create Event", 
                "Failed", 
                f"Raw input: '{analysis.get('raw_input', '')[:60]}'. Error: {sync_result.get('error', '')}",
                "Google Calendar"
            )
            print(f"❌ Failed to create event: {sync_result.get('error')}", flush=True)
    
    else:
        # ==========================================
        # ROUTE TO NOTION
        # ==========================================
        print(f"📓 Routing to Notion: {title}", flush=True)
        summary["destination"] = "Notion"
        
        # Check Notion connection
        notion_status = notion_service.get_auth_status()
        if not notion_status.get("connected"):
            result["notion_created"] = False
            result["notion_error"] = "Notion not connected. Please connect Notion in settings."
            add_log_entry("Create Page", "Failed", "Notion not connected", "Notion")
            summary["left_empty"].append({"reason": "Notion not connected"})
        else:
            # Get databases
            databases = notion_service.fetch_databases_in_page(notion_service.get_selected_page_id())
            
            if not databases:
                result["notion_created"] = False
                result["notion_error"] = "No Notion databases found. Please share a page with databases with this app."
                add_log_entry(
                    "Create Page", 
                    "Failed", 
                    f"No databases found. Raw input: '{analysis.get('raw_input', '')[:100]}'. Please share Notion pages with your integration.", 
                    "Notion"
                )
            else:
                # Select best database using AI - now returns detailed result
                db_selection = ai_service.select_best_database(analysis, databases)
                
                # Get log database early for writing failures too
                log_db_id = notion_service.detect_log_database(databases)
                
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
                        f"Detailed analysis: {analysis.get('detailed_analysis', 'N/A')[:200]}. "
                        f"Available DBs: {', '.join(db_names)}. "
                        f"Reason: {db_selection.get('reason', 'Unknown')}"
                    )
                    
                    add_log_entry("Create Page", "Failed", failure_details, "Notion")
                    
                    # Write failure to Notion log database too
                    if log_db_id:
                        log_data = {
                            "action": f"FAILED: {title}",
                            "timestamp": datetime.now().astimezone().isoformat(),
                            "result": "Failed",
                            "database": "None (no match)",
                            "details": failure_details
                        }
                        notion_service.write_log_entry(log_db_id, log_data)
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
                    properties = notion_service.fetch_database_properties(db_id)
                    
                    # DYNAMIC AI PROPERTY MAPPING - no hardcoded aliases
                    print(f"🤖 AI mapping properties dynamically...", flush=True)
                    mapping_result = ai_service.map_properties_dynamically(analysis, properties)
                    mapped_properties = mapping_result["properties"]
                    summary["filled_from_user"] = mapping_result["filled_from_user"]
                    summary["left_empty"] = mapping_result["left_empty"]
                    summary["mapping_reasoning"] = mapping_result.get("ai_reasoning", "")
                    
                    print(f"📝 Mapped {len(mapped_properties)} properties", flush=True)
                    
                    # DYNAMIC AI RESEARCHABLE IDENTIFICATION
                    if mapping_result["left_empty"]:
                        print(f"🔍 AI identifying researchable properties...", flush=True)
                        researchable = ai_service.identify_researchable_properties(
                            analysis, properties, mapping_result["left_empty"]
                        )
                        
                        # AI enrichment for researchable properties
                        if researchable:
                            print(f"🔬 Enriching {len(researchable)} researchable properties with AI...", flush=True)
                            enriched_data = ai_service.enrich_properties(analysis, researchable)
                            
                            if enriched_data:
                                enrich_result = notion_service.apply_enriched_properties(
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
                    create_result = notion_service.create_page(db_id, mapped_properties)
                    
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
                            f"Detailed analysis: {analysis.get('detailed_analysis', 'N/A')[:150]}. "
                            f"Database: {db_title}. "
                            f"Mapped by AI: {', '.join(filled_props) if filled_props else 'None'}. "
                            f"Researched by AI: {', '.join(ai_props) if ai_props else 'None'}. "
                            f"Mapping reasoning: {summary.get('mapping_reasoning', 'N/A')[:100]}"
                        )
                        
                        add_log_entry("Create Page", "Success", log_details, "Notion")
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
                            notion_service.write_log_entry(log_db_id, log_data)
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
                        
                        add_log_entry("Create Page", "Failed", failure_details, "Notion")
                        
                        # Write failure to Notion log database
                        if log_db_id:
                            log_data = {
                                "action": f"FAILED: {title}",
                                "timestamp": datetime.now().astimezone().isoformat(),
                                "result": "Failed",
                                "database": db_title,
                                "details": failure_details
                            }
                            notion_service.write_log_entry(log_db_id, log_data)
                            print(f"📝 Failure logged to Notion", flush=True)
                        
                        print(f"❌ Failed to create Notion page: {create_result.get('error')}", flush=True)
    
    # Add summary and auth status to result
    result["summary"] = summary
    result["google_status"] = external_service.get_google_auth_status()
    result["notion_status"] = notion_service.get_auth_status()
    
    return result


@app.post("/process-text")
async def process_text(input_data: TextInput):
    """
    Process text input with the capture flow.
    
    Flow:
    1. AI Analysis: Determine if event or other content
    2. Route: Events → Google Calendar, Other → Notion
    """
    try:
        text = input_data.text.strip()
        if not text:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "Text input is empty"}
            )
        
        print(f"📝 Processing text input ({len(text)} chars)...", flush=True)
        
        # Step 1: AI Analysis
        print("🤖 Step 1: AI Analysis...", flush=True)
        analysis = ai_service.analyze_text_input(text)
        
        if not analysis.get("success", False):
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "step": "ai_analysis",
                    "message": analysis.get("error", "AI analysis failed")
                }
            )
        
        # Step 2: Process and route
        result = process_capture_result(analysis, "text")
        result["input_type"] = "text"
        result["input_length"] = len(text)
        
        return result
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )


@app.post("/upload-screenshot")
async def upload_screenshot(screenshot: UploadFile = File(...)):
    """
    Main capture processing endpoint.
    
    Flow:
    1. AI Layer: OCR + GPT-4o analysis → determines event vs other
    2. Route: Events → Google Calendar, Other → Notion
    """
    try:
        # Read image data
        image_data = await screenshot.read()
        image_size = len(image_data)
        
        print(f"📷 Processing screenshot ({image_size} bytes)...", flush=True)
        
        # Step 1: AI Analysis
        print("🤖 Step 1: AI Analysis...", flush=True)
        analysis, ocr_text = ai_service.process_capture(image_data)
        
        if not analysis.get("success", False):
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "step": "ai_analysis",
                    "message": analysis.get("error", "AI analysis failed")
                }
            )
        
        # Step 2: Process and route
        result = process_capture_result(analysis, "screenshot")
        result["input_type"] = "screenshot"
        result["filename"] = screenshot.filename
        result["content_type"] = screenshot.content_type
        result["size_bytes"] = image_size
        result["transcribed_text"] = ocr_text
        
        return result
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )


# ============================================
# SESSION LOG ENDPOINTS
# ============================================

@app.get("/logs")
def get_logs():
    """Get in-memory session logs"""
    return {
        "logs": session_log,
        "count": len(session_log)
    }

@app.delete("/logs")
def clear_logs():
    """Clear session logs"""
    session_log.clear()
    return {"status": "success", "message": "Logs cleared"}


# ============================================
# GOOGLE AUTH ENDPOINTS
# ============================================

@app.get("/google/auth/status")
def google_auth_status():
    """Check Google Calendar connection status"""
    return external_service.get_google_auth_status()


@app.get("/google/auth/url")
def google_auth_url():
    """Get Google OAuth authorization URL"""
    result = external_service.get_google_auth_url()
    if not result:
        return JSONResponse(
            status_code=500,
            content={"error": "Google OAuth credentials file not found"}
        )
    return result


@app.get("/google/auth/callback")
async def google_auth_callback(request: Request):
    """Handle Google OAuth callback"""
    try:
        code = request.query_params.get('code')
        state = request.query_params.get('state')
        
        credentials = external_service.handle_google_callback(code, state)
        
        if credentials:
            add_log_entry("Google Auth", "Success", "Connected to Google Calendar", "Google")
        
        return RedirectResponse(url="http://127.0.0.1:8000/google/auth/success")
        
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/google/auth/success")
def google_auth_success():
    """Success page after OAuth"""
    return {
        "status": "success",
        "message": "Google Calendar connected successfully! You can close this window."
    }


@app.post("/google/auth/logout")
def google_auth_logout():
    """Disconnect Google Calendar"""
    try:
        external_service.clear_google_credentials()
        add_log_entry("Google Auth", "Logout", "Disconnected from Google Calendar", "Google")
        return {"status": "success", "message": "Google Calendar disconnected"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.delete("/google/delete-event/{event_id}")
def delete_calendar_event(event_id: str):
    """Delete a Google Calendar event"""
    result = external_service.delete_google_calendar_event(event_id)
    if result.get("success"):
        add_log_entry("Delete Event", "Success", f"Deleted event: {event_id}", "Google Calendar")
        return result
    else:
        return JSONResponse(status_code=500, content=result)


@app.post("/google/test-event")
def test_calendar_event():
    """Create a test calendar event"""
    from datetime import timedelta, timezone
    
    credentials = external_service.get_google_credentials()
    if not credentials:
        return JSONResponse(status_code=400, content={"error": "Google Calendar not connected"})
    
    local_now = datetime.now().astimezone()
    start = local_now.replace(hour=14, minute=0, second=0, microsecond=0)
    if local_now.hour >= 14:
        start += timedelta(days=1)
    
    test_entry = {
        "category": "event",
        "title": "Test Event from Notion Capture",
        "description": "This is a test event to verify calendar integration.",
        "start_date": start.isoformat(),
        "end_date": (start + timedelta(hours=1)).isoformat(),
    }
    
    result = external_service.sync_to_google_calendar(test_entry)
    
    if result.get("success"):
        add_log_entry("Test Event", "Success", "Test event created", "Google Calendar")
        return {
            "status": "success",
            "message": "Test event created",
            **result
        }
    else:
        return JSONResponse(status_code=500, content=result)


# ============================================
# NOTION STATUS ENDPOINT
# ============================================

@app.get("/notion/auth/status")
def notion_auth_status():
    """Check Notion connection status (uses NOTION_API_KEY from env)"""
    return notion_service.get_auth_status()


# ============================================
# NOTION DATA ENDPOINTS
# ============================================

@app.get("/notion/pages")
def get_notion_pages():
    """Get all accessible Notion pages"""
    if not notion_service.get_auth_status().get("connected"):
        return JSONResponse(status_code=400, content={"error": "Notion not connected"})
    
    pages = notion_service.fetch_pages()
    return {"pages": pages, "count": len(pages)}


@app.get("/notion/databases")
def get_notion_databases(page_id: Optional[str] = None):
    """Get all databases, optionally filtered by parent page"""
    if not notion_service.get_auth_status().get("connected"):
        return JSONResponse(status_code=400, content={"error": "Notion not connected"})
    
    databases = notion_service.fetch_databases_in_page(page_id)
    return {"databases": databases, "count": len(databases)}


@app.get("/notion/databases/{database_id}/properties")
def get_database_properties(database_id: str):
    """Get properties schema for a specific database"""
    if not notion_service.get_auth_status().get("connected"):
        return JSONResponse(status_code=400, content={"error": "Notion not connected"})
    
    properties = notion_service.fetch_database_properties(database_id)
    return {"database_id": database_id, "properties": properties, "count": len(properties)}


@app.post("/notion/select-page")
def select_notion_page(page_id: str):
    """Set the selected page for database operations"""
    if not notion_service.get_auth_status().get("connected"):
        return JSONResponse(status_code=400, content={"error": "Notion not connected"})
    
    notion_service.set_selected_page(page_id)
    return {"status": "success", "selected_page_id": page_id}


# ============================================
# LEGACY ENDPOINTS (for backwards compatibility)
# ============================================

@app.get("/categories")
def get_categories():
    """Get all available categories (legacy endpoint)"""
    categories = ai_service.get_categories()
    return {
        "categories": [{"name": k, "description": v} for k, v in categories.items()],
        "count": len(categories)
    }


@app.post("/ingest")
def ingest(payload: dict):
    """Legacy endpoint"""
    return {
        "type": "other",
        "title": "Example from Notion Capture",
        "details": "This endpoint is deprecated. Use /upload-screenshot or /process-text.",
        "received_payload": payload,
    }
