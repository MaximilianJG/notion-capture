"""
Capture endpoints - Screenshot and text processing
"""
import json
from typing import Optional
from fastapi import APIRouter, File, UploadFile, Header, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.services.ai.analyzer import analyze_text, process_capture
from app.services.capture import process_capture_result

router = APIRouter()


class TextInput(BaseModel):
    """Text input with optional credentials"""
    text: str
    notion_api_key: Optional[str] = None
    notion_selected_page_id: Optional[str] = None
    google_tokens: Optional[str] = None  # JSON string


def _parse_google_tokens(tokens_str: Optional[str]) -> Optional[dict]:
    """Parse Google tokens from JSON string"""
    if not tokens_str:
        return None
    try:
        return json.loads(tokens_str)
    except:
        return None


@router.post("/process-text")
async def process_text_endpoint(
    input_data: TextInput,
    x_notion_api_key: Optional[str] = Header(None, alias="X-Notion-Api-Key"),
    x_notion_page_id: Optional[str] = Header(None, alias="X-Notion-Page-Id"),
    x_google_tokens: Optional[str] = Header(None, alias="X-Google-Tokens")
):
    """
    Process text input with the capture flow.
    
    Credentials can be provided via:
    - Request body (notion_api_key, google_tokens)
    - Headers (X-Notion-Api-Key, X-Google-Tokens)
    
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
        
        # Get credentials from body or headers
        notion_api_key = input_data.notion_api_key or x_notion_api_key
        notion_page_id = input_data.notion_selected_page_id or x_notion_page_id
        google_tokens = _parse_google_tokens(input_data.google_tokens) or _parse_google_tokens(x_google_tokens)
        
        print(f"📝 Processing text input ({len(text)} chars)...", flush=True)
        
        # Step 1: AI Analysis
        print("🤖 Step 1: AI Analysis...", flush=True)
        analysis = analyze_text(text)
        
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
        result = process_capture_result(
            analysis,
            "text",
            notion_api_key=notion_api_key,
            google_tokens=google_tokens,
            selected_page_id=notion_page_id
        )
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


@router.post("/upload-screenshot")
async def upload_screenshot_endpoint(
    screenshot: UploadFile = File(...),
    notion_api_key: Optional[str] = Form(None),
    notion_selected_page_id: Optional[str] = Form(None),
    google_tokens: Optional[str] = Form(None),
    x_notion_api_key: Optional[str] = Header(None, alias="X-Notion-Api-Key"),
    x_notion_page_id: Optional[str] = Header(None, alias="X-Notion-Page-Id"),
    x_google_tokens: Optional[str] = Header(None, alias="X-Google-Tokens")
):
    """
    Process screenshot with the capture flow.
    
    Credentials can be provided via:
    - Form data (notion_api_key, google_tokens)
    - Headers (X-Notion-Api-Key, X-Google-Tokens)
    
    Flow:
    1. AI Layer: OCR + GPT-4o analysis → determines event vs other
    2. Route: Events → Google Calendar, Other → Notion
    """
    try:
        # Read image data
        image_data = await screenshot.read()
        image_size = len(image_data)
        
        # Get credentials from form or headers
        notion_key = notion_api_key or x_notion_api_key
        notion_page = notion_selected_page_id or x_notion_page_id
        g_tokens = _parse_google_tokens(google_tokens) or _parse_google_tokens(x_google_tokens)
        
        print(f"📷 Processing screenshot ({image_size} bytes)...", flush=True)
        
        # Step 1: AI Analysis
        print("🤖 Step 1: AI Analysis...", flush=True)
        analysis, ocr_text = process_capture(image_data)
        
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
        result = process_capture_result(
            analysis,
            "screenshot",
            notion_api_key=notion_key,
            google_tokens=g_tokens,
            selected_page_id=notion_page
        )
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

