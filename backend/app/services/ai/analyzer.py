"""
AI Analyzer - OCR and content analysis
"""
import io
import base64
import json
from typing import Dict, Any, Tuple
from PIL import Image
import pytesseract

from app.core import get_openai_client, get_local_datetime_context, log_ai_prompt, log_ai_response
from app.services.ai.prompts.loader import render_prompt


def extract_text_ocr(image_data: bytes) -> str:
    """Extract text from image using OCR"""
    try:
        image = Image.open(io.BytesIO(image_data))
        text = pytesseract.image_to_string(image)
        return text.strip()
    except Exception as e:
        print(f"OCR Error: {e}")
        return ""


def _parse_ai_response(response: str) -> Dict[str, Any]:
    """Parse and validate AI response JSON"""
    try:
        json_start = response.find('{')
        json_end = response.rfind('}') + 1
        
        if json_start >= 0 and json_end > json_start:
            data = json.loads(response[json_start:json_end])
            
            category = data.get("category", "other")
            if category not in ["event", "other"]:
                category = "other"
            data["category"] = category
            
            if "confidence" in data:
                data["ai_confidence"] = float(data.pop("confidence", 0.5))
            else:
                data["ai_confidence"] = 0.5
            
            return data
        else:
            raise ValueError("No JSON found")
            
    except (json.JSONDecodeError, ValueError) as e:
        print(f"Parse error: {e}")
        return {
            "category": "other",
            "title": "Parse Error",
            "content": response,
            "content_type": "note",
            "detailed_analysis": "Failed to parse AI response",
            "ai_confidence": 0.0,
        }


def analyze_text(text: str) -> Dict[str, Any]:
    """Analyze text input with GPT-4o."""
    client = get_openai_client()
    if not client:
        return {"success": False, "error": "OpenAI API key not configured", "category": None}
    
    dt_context = get_local_datetime_context()
    
    prompt = render_prompt(
        "analyze_text",
        datetime_formatted=dt_context['formatted'],
        datetime_iso=dt_context['datetime_iso'],
        timezone=dt_context['timezone'],
        timezone_offset=dt_context['timezone_offset'],
        text=text
    )

    try:
        log_ai_prompt("analyze_text", prompt)
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1500
        )
        
        ai_response_text = response.choices[0].message.content
        log_ai_response("analyze_text", ai_response_text)
        
        result = _parse_ai_response(ai_response_text)
        result["raw_input"] = text
        result["source_text"] = text
        result["capture_datetime"] = dt_context["datetime_iso"]
        result["capture_date"] = dt_context["date"]
        result["capture_time"] = dt_context["time"]
        result["capture_timezone"] = dt_context["timezone"]
        result["success"] = True
        
        print(f"AI categorized text as: {result.get('category')} (confidence: {result.get('ai_confidence', 0):.2f})")
        
        return result
        
    except Exception as e:
        print(f"AI Text Analysis Error: {e}")
        dt = get_local_datetime_context()
        return {
            "success": True,
            "category": "other",
            "title": "AI Analysis Failed",
            "content": text,
            "content_type": "note",
            "detailed_analysis": f"Failed to analyze: {str(e)}",
            "raw_input": text,
            "source_text": text,
            "capture_datetime": dt["datetime_iso"],
            "capture_date": dt["date"],
            "capture_time": dt["time"],
            "ai_confidence": 0.0,
        }


def analyze_screenshot(image_data: bytes, ocr_text: str) -> Dict[str, Any]:
    """Analyze screenshot with GPT-4o Vision."""
    client = get_openai_client()
    if not client:
        return {"success": False, "error": "OpenAI API key not configured", "category": None}
    
    dt_context = get_local_datetime_context()
    
    prompt = render_prompt(
        "analyze_screenshot",
        datetime_formatted=dt_context['formatted'],
        datetime_iso=dt_context['datetime_iso'],
        timezone=dt_context['timezone'],
        timezone_offset=dt_context['timezone_offset'],
        ocr_text=ocr_text if ocr_text else "(No text detected)"
    )

    try:
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        
        log_ai_prompt("analyze_screenshot", prompt + "\n[+ IMAGE DATA]")
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}}
                ]
            }],
            max_tokens=1500
        )
        
        ai_response_text = response.choices[0].message.content
        log_ai_response("analyze_screenshot", ai_response_text)
        
        result = _parse_ai_response(ai_response_text)
        result["raw_input"] = ocr_text
        result["source_text"] = ocr_text
        result["capture_datetime"] = dt_context["datetime_iso"]
        result["capture_date"] = dt_context["date"]
        result["capture_time"] = dt_context["time"]
        result["capture_timezone"] = dt_context["timezone"]
        result["success"] = True
        
        return result
        
    except Exception as e:
        print(f"AI Analysis Error: {e}")
        dt = get_local_datetime_context()
        return {
            "success": True,
            "category": "other",
            "title": "AI Analysis Failed",
            "content": ocr_text,
            "content_type": "note",
            "detailed_analysis": f"Failed to analyze: {str(e)}",
            "raw_input": ocr_text,
            "source_text": ocr_text,
            "capture_datetime": dt["datetime_iso"],
            "capture_date": dt["date"],
            "capture_time": dt["time"],
            "ai_confidence": 0.0,
        }


def process_capture(image_data: bytes) -> Tuple[Dict[str, Any], str]:
    """Full capture processing: OCR + AI analysis"""
    ocr_text = extract_text_ocr(image_data)
    print(f"OCR extracted {len(ocr_text)} characters")
    
    analysis = analyze_screenshot(image_data, ocr_text)
    print(f"AI categorized as: {analysis.get('category')} (confidence: {analysis.get('ai_confidence', 0):.2f})")
    
    return analysis, ocr_text
