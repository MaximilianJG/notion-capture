"""
AI Service - Handles all AI/ML operations (OCR, GPT-4o analysis, enrichment)
Everything is dynamic and AI-driven - no hardcoded mappings or rules.
"""
import os
import io
import base64
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple, List
from PIL import Image
import pytesseract


# Enable detailed AI logging
AI_DEBUG_LOGGING = True


def log_ai_prompt(method_name: str, prompt: str):
    """Log AI prompt to terminal"""
    if AI_DEBUG_LOGGING:
        print(f"\n{'='*60}")
        print(f"🤖 AI PROMPT [{method_name}]")
        print(f"{'='*60}")
        print(prompt[:2000] + "..." if len(prompt) > 2000 else prompt)
        print(f"{'='*60}\n")


def log_ai_response(method_name: str, response: str):
    """Log AI response to terminal"""
    if AI_DEBUG_LOGGING:
        print(f"\n{'-'*60}")
        print(f"📨 AI RESPONSE [{method_name}]")
        print(f"{'-'*60}")
        print(response[:2000] + "..." if len(response) > 2000 else response)
        print(f"{'-'*60}\n")


def get_local_datetime_context() -> Dict[str, str]:
    """Get current datetime in local timezone with full context."""
    local_now = datetime.now().astimezone()
    return {
        "datetime_iso": local_now.isoformat(),
        "date": local_now.strftime("%Y-%m-%d"),
        "time": local_now.strftime("%H:%M:%S"),
        "timezone": str(local_now.tzinfo),
        "timezone_offset": local_now.strftime("%z"),
        "weekday": local_now.strftime("%A"),
        "formatted": local_now.strftime("%A, %B %d, %Y at %I:%M %p %Z")
    }


class AIService:
    """Service for AI-powered analysis - fully dynamic, no hardcoded rules"""
    
    _instance = None
    _client = None
    
    CATEGORIES = {
        "event": "Calendar events with date, time, location",
        "other": "Everything else - goes to Notion"
    }
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def _get_client(self):
        """Get or create OpenAI client (lazy initialization)"""
        if self._client is None:
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                from openai import OpenAI
                self._client = OpenAI(api_key=api_key)
        return self._client
    
    def get_categories(self) -> Dict[str, str]:
        return self.CATEGORIES
    
    def get_category_names(self) -> List[str]:
        return list(self.CATEGORIES.keys())
    
    def extract_text(self, image_data: bytes) -> str:
        """Extract text from image using OCR"""
        try:
            image = Image.open(io.BytesIO(image_data))
            text = pytesseract.image_to_string(image)
            return text.strip()
        except Exception as e:
            print(f"OCR Error: {e}")
            return ""
    
    def analyze_screenshot(self, image_data: bytes, ocr_text: str) -> Dict[str, Any]:
        """Analyze screenshot with GPT-4o Vision."""
        client = self._get_client()
        if not client:
            return {"success": False, "error": "OpenAI API key not configured", "category": None}
        
        dt_context = get_local_datetime_context()
        
        prompt = f"""Analyze this screenshot and extract structured information.

CURRENT DATE/TIME (Local Timezone):
- Now: {dt_context['formatted']}
- ISO: {dt_context['datetime_iso']}
- Timezone: {dt_context['timezone']} ({dt_context['timezone_offset']})

OCR EXTRACTED TEXT:
{ocr_text if ocr_text else "(No text detected)"}

INSTRUCTIONS:
Analyze and determine if this is:
1. An EVENT - Something with a date/time for a calendar
2. SOMETHING ELSE - Any other content for Notion

Provide a DETAILED ANALYSIS explaining what this input represents, its context, and meaning.

RESPOND WITH JSON ONLY:

For EVENTS:
{{
    "category": "event",
    "confidence": 0.0-1.0,
    "title": "event title",
    "description": "event description",
    "detailed_analysis": "In-depth explanation of what this input represents, what it means, the context, and any important details about its significance",
    "start_time": "ISO 8601 local datetime",
    "end_time": "ISO 8601 local datetime or null",
    "location": "location or null",
    "extracted_fields": {{...any other structured data...}}
}}

For OTHER:
{{
    "category": "other",
    "confidence": 0.0-1.0,
    "title": "descriptive title",
    "description": "brief description",
    "detailed_analysis": "In-depth explanation of what this input represents, what it means, the context, and any important details. For movies, explain the movie. For books, explain the book. Be thorough.",
    "content": "main content",
    "content_type": "movie|book|task|note|recipe|article|music|contact|other",
    "extracted_fields": {{...any other structured data you can extract...}}
}}

Return ONLY valid JSON."""

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
            
            result = self._parse_ai_response(ai_response_text)
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
    
    def _parse_ai_response(self, response: str) -> Dict[str, Any]:
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
    
    def process_capture(self, image_data: bytes) -> Tuple[Dict[str, Any], str]:
        """Full capture processing: OCR + AI analysis"""
        ocr_text = self.extract_text(image_data)
        print(f"OCR extracted {len(ocr_text)} characters")
        
        analysis = self.analyze_screenshot(image_data, ocr_text)
        print(f"AI categorized as: {analysis.get('category')} (confidence: {analysis.get('ai_confidence', 0):.2f})")
        
        return analysis, ocr_text
    
    def analyze_text_input(self, text: str) -> Dict[str, Any]:
        """Analyze text input with GPT-4o."""
        client = self._get_client()
        if not client:
            return {"success": False, "error": "OpenAI API key not configured", "category": None}
        
        dt_context = get_local_datetime_context()
        
        prompt = f"""Analyze this text input and extract structured information.

CURRENT DATE/TIME (Local Timezone):
- Now: {dt_context['formatted']}
- ISO: {dt_context['datetime_iso']}
- Timezone: {dt_context['timezone']} ({dt_context['timezone_offset']})

USER INPUT TEXT:
"{text}"

INSTRUCTIONS:
Analyze and determine if this is:
1. A CALENDAR EVENT - Something that happens at a SPECIFIC DATE AND TIME, or implies attendance/presence at a set moment
2. SOMETHING ELSE - Any other content for Notion

CLASSIFICATION RULES (CRITICAL):
CALENDAR EVENT requires BOTH:
- A specific DATE
- A specific TIME or implied attendance at a moment (flight, meeting, appointment, reservation, call scheduled at X)

Examples of CALENDAR EVENTS:
- "Meeting with John at 3pm tomorrow" → EVENT (date + time)
- "Dentist appointment Friday 10am" → EVENT (date + time + attendance)
- "Team call at 2:30" → EVENT (implies time)
- "Dinner reservation 7pm Saturday" → EVENT (date + time + attendance)

Examples of TASKS (NOT events):
- "Buy milk tomorrow" → TASK (has date but no specific time - flexible when to do it)
- "Call mom" → TASK (no date/time specified)
- "Respond to email by Friday" → TASK (deadline, not a scheduled moment)
- "Finish report this week" → TASK (timeframe, not a specific moment)
- "Pick up dry cleaning tomorrow" → TASK (date but no time - do it anytime that day)

KEY DISTINCTION: 
- EVENT = You must be somewhere or do something AT a specific moment
- TASK = Something to complete, flexible when exactly you do it

Provide a DETAILED ANALYSIS explaining what this input represents, its context, and meaning.
For relative dates ("tomorrow", "next Monday"): Calculate from today's date.

TITLE RULES - Create an actionable, meaningful title:

PRINCIPLE: The title should be what someone would write as a task/item name - clear, actionable, and specific.

DO:
- Fix typos and grammar (e.g., "respondt o" → "respond to")
- Use proper capitalization (Title Case)
- Keep action verbs that describe WHAT to do (respond, call, buy, check, review, etc.)
- Keep specific details (names, places, subjects)
- Keep prepositions when they add meaning ("to", "for", "with", "about")

REMOVE:
- Generic category labels: "task", "note", "reminder", "item", "thing", "todo"
- Meta-instructions to the app: "add", "save", "track", "log" (when they're just telling the app what to do)
- Redundant words that don't add meaning

BE SMART:
- "respond to station f women" → "Respond to Station F Women" (keep the action and specifics)
- "add milk to shopping list" → "Milk" or "Buy Milk" (remove "add" and "to shopping list" category)
- "complete stern test" → "Stern Test" (remove "complete" if it's just a meta-action)
- "watch inception movie" → "Inception" (remove "watch" and "movie" - the title is the entity)
- "call mom about dinner" → "Call Mom About Dinner" (keep - this is the actual action)
- "remember to drink water" → "Drink Water" (the action is drinking, not remembering)

Examples:
  * "respondt o station f women" → "Respond to Station F Women"
  * "add complete stern test to tasks" → "Complete Stern Test"
  * "watch inception" → "Inception"
  * "call mom tomorrow" → "Call Mom"
  * "buy groceries for dinner" → "Buy Groceries for Dinner"

RESPOND WITH JSON ONLY:

For EVENTS:
{{
    "category": "event",
    "confidence": 0.0-1.0,
    "title": "actionable event title - fix typos, remove category words, keep meaningful details (see TITLE RULES)",
    "description": "event description",
    "detailed_analysis": "In-depth explanation of what this input represents",
    "start_time": "ISO 8601 local datetime",
    "end_time": "ISO 8601 local datetime or null",
    "location": "location or null",
    "extracted_fields": {{...any other data...}}
}}

For OTHER:
{{
    "category": "other",
    "confidence": 0.0-1.0,
    "title": "actionable title - fix typos, remove category words, keep meaningful actions and specifics (see TITLE RULES)",
    "description": "brief description",
    "detailed_analysis": "In-depth explanation of what this input represents, what it means, the context, and any important details.",
    "content": "the input text with grammar fixed",
    "content_type": "movie|book|task|note|recipe|article|music|contact|other",
    "do_date": null,
    "deadline": null,
    "extracted_fields": {{...any other structured data...}}
}}

DATE EXTRACTION RULES (CRITICAL - READ CAREFULLY):

do_date (when to do it):
- ONLY set if user specifies WHEN they will do something
- Trigger words: "tomorrow", "on Monday", "this weekend", "tonight", specific dates
- Example: "Buy milk tomorrow" → do_date: "2024-12-28" (tomorrow's date)

deadline (hard cutoff):
- ONLY set if user EXPLICITLY uses deadline language
- REQUIRED trigger words: "by", "due", "deadline", "before", "until", "no later than"
- If none of these words appear, deadline MUST be null
- Example: "Submit report by Friday" → deadline: Friday's date
- Example: "Buy milk tomorrow" → deadline: null (NO "by/due/deadline" word!)

STRICT RULES:
1. "tomorrow", "Monday", "next week" WITHOUT "by/due" = do_date, NOT deadline
2. deadline requires EXPLICIT deadline language - do not infer it
3. If unsure, leave as null
4. Both can be null if no date mentioned

Examples:
  * "Buy milk tomorrow" → do_date: tomorrow, deadline: null (no "by/due")
  * "Submit report by Friday" → do_date: null, deadline: Friday (has "by")
  * "Finish homework due Monday" → do_date: null, deadline: Monday (has "due")  
  * "Work on project Monday, due Wednesday" → do_date: Monday, deadline: Wednesday
  * "Call mom" → do_date: null, deadline: null
  * "Do laundry this weekend" → do_date: weekend, deadline: null (no "by/due")

Return ONLY valid JSON."""

        try:
            log_ai_prompt("analyze_text_input", prompt)
            
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1500
            )
            
            ai_response_text = response.choices[0].message.content
            log_ai_response("analyze_text_input", ai_response_text)
            
            result = self._parse_ai_response(ai_response_text)
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
    
    def map_properties_dynamically(
        self,
        user_data: Dict[str, Any],
        database_properties: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Use AI to dynamically map user data to database properties.
        No hardcoded aliases - AI reasons about each property.
        """
        client = self._get_client()
        if not client:
            return {"properties": {}, "filled_from_user": [], "left_empty": list(database_properties.keys()), "ai_reasoning": "OpenAI not available"}
        
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
        
        # Build user data context
        raw_input = user_data.get("raw_input", user_data.get("source_text", ""))
        
        prompt = f"""You are mapping user input data to Notion database properties.

RAW USER INPUT (exact text entered):
"{raw_input}"

CAPTURE DATETIME (Local Timezone - FOR REFERENCE ONLY):
- DateTime: {dt_context['datetime_iso']}
- Date: {dt_context['date']}
- Time: {dt_context['time']}
- Timezone: {dt_context['timezone']}
NOTE: This capture datetime is ONLY for properties explicitly about "when this was captured/added" (e.g., "Date Added", "Created Date"). DO NOT use it for due dates, deadlines, or event dates.

ANALYZED USER DATA:
{json.dumps({k: v for k, v in user_data.items() if k not in ['raw_response', 'success'] and v is not None}, indent=2, default=str)}

DATABASE PROPERTIES TO FILL:
{json.dumps(props_info, indent=2)}

INSTRUCTIONS:
For EACH property in the database, evaluate if ANY of the user data should fill it.
Consider:
- Property name meaning (e.g., "Raw Input" should get the exact user input)
- Property type compatibility
- Semantic matching (e.g., "Director" property + movie content → look for director info)
- For select/status types, use one of the provided options if available

CRITICAL RULE - DATE PROPERTIES:
DO NOT fill date properties UNLESS the user input explicitly mentions a date.

DATE TYPE DISTINCTION (VERY IMPORTANT):
1. DO DATE / SCHEDULED DATE = When something WILL BE DONE or is scheduled
   - Property names that indicate WHEN TO DO IT (be flexible with naming):
     "do date", "date", "start date", "start", "start time", "scheduled", "scheduled date", 
     "planned", "planned date", "when", "on date", "task date", "action date", "work date" etc. (use semantic reasoning to determine if it's a do date)
   - Fill with: user_data["do_date"] if present
   - Example input: "Buy milk tomorrow" → do_date is tomorrow

2. DEADLINE / DUE DATE = When something MUST BE DONE BY (hard cutoff)
   - Property names that indicate MUST BE COMPLETED BY:
     "deadline", "due date", "due", "due by", "must complete by", "end date", "finish by",
     "complete by", "submission date", "cutoff", "final date" etc. (use semantic reasoning to determine if it's a deadline)
   - Fill with: user_data["deadline"] if present
   - Example input: "Submit report by Friday" → deadline is Friday

3. CREATED/CAPTURED DATE = When the entry was captured
   - Property names like: "date added", "created date", "captured date", "added on", "created", "capture date"
   - You MAY use capture datetime for these

USE SEMANTIC REASONING for property names not listed above:
- Does the property name imply "when to work on it"? → Use do_date
- Does the property name imply "must be done by"? → Use deadline
- Does the property name imply "when was this created"? → Use capture datetime

DO NOT mix up do_date and deadline - they are different concepts!
- "Buy milk tomorrow" → do_date: tomorrow, deadline: null
- "Submit by Friday" → do_date: null, deadline: Friday
- "Work on Monday, due Wednesday" → do_date: Monday, deadline: Wednesday

DO NOT use capture datetime for do_date or deadline properties.
DO NOT infer or guess dates. If not explicitly provided, leave empty.

Be thorough - map everything that makes sense, but be conservative with dates.

RESPOND WITH JSON:
{{
    "mappings": [
        {{
            "property": "Property Name",
            "value": "the value to set",
            "source": "which user_data field or 'inferred'",
            "reasoning": "why this mapping makes sense"
        }},
        ...
    ],
    "unmapped_properties": ["Property1", "Property2"],
    "overall_reasoning": "summary of mapping decisions"
}}

Return ONLY valid JSON."""

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
                        
                        # Convert to Notion format
                        notion_value = self._convert_to_notion_value(prop_type, value, prop_info)
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
    
    def _convert_to_notion_value(self, prop_type: str, value: Any, prop_info: Dict) -> Optional[Dict]:
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
    
    def identify_researchable_properties(
        self,
        user_data: Dict[str, Any],
        database_properties: Dict[str, Dict[str, Any]],
        empty_properties: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Use AI to dynamically identify which empty properties could be researched/filled.
        No hardcoded indicators - AI reasons about each property.
        """
        client = self._get_client()
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
        
        prompt = f"""Analyze which empty database properties could be researched and filled with additional information.

USER INPUT:
"{raw_input}"

CONTENT ANALYSIS:
- Title: {title}
- Type: {content_type}
- Detailed Analysis: {detailed_analysis}

EMPTY PROPERTIES (not yet filled):
{json.dumps(empty_props_info, indent=2)}

INSTRUCTIONS:
For each empty property, determine if it's "researchable" - meaning:
1. The property asks for factual information that can be looked up
2. Given the user's input (e.g., a movie title), this information could be researched
3. Examples: Director, Author, Year, Genre, Rating, Duration, Publisher, Release Year, etc.

DO NOT mark as researchable:
- Properties that are purely user-preference (like personal rating)
- Properties that require user-specific info
- Properties that are subjective notes

RESPOND WITH JSON:
{{
    "researchable": [
        {{
            "property": "Property Name",
            "type": "property_type",
            "options": [...] or null,
            "reasoning": "why this can be researched given the input"
        }}
    ],
    "not_researchable": [
        {{
            "property": "Property Name",
            "reasoning": "why this cannot/should not be auto-filled"
        }}
    ]
}}

Return ONLY valid JSON."""

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
        self,
        user_data: Dict[str, Any],
        researchable_properties: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Use AI to research and fill researchable properties.
        """
        client = self._get_client()
        if not client or not researchable_properties:
            return {}
        
        dt_context = get_local_datetime_context()
        
        raw_input = user_data.get("raw_input", user_data.get("source_text", ""))
        title = user_data.get("title", "")
        content_type = user_data.get("content_type", "")
        detailed_analysis = user_data.get("detailed_analysis", "")
        
        prompt = f"""Research and fill the following properties based on the user's input.

USER INPUT:
"{raw_input}"

CONTENT:
- Title: {title}
- Type: {content_type}
- Analysis: {detailed_analysis}

CURRENT DATE: {dt_context['date']}

PROPERTIES TO RESEARCH AND FILL:
{json.dumps(researchable_properties, indent=2)}

INSTRUCTIONS:
1. Research each property based on the content (e.g., for a movie, look up director, year, etc.)
2. For select types, use one of the provided options if available
3. For dates, use ISO format (YYYY-MM-DD)
4. Only provide values you're confident about
5. Set to null if you cannot determine the value

DATE PROPERTIES - BE SMART:
- FACTUAL dates CAN be researched: release year, publication date, founding date, birth date, etc.
- USER-SPECIFIC dates should NOT be inferred: deadline, due date, do date, scheduled date, start date
- If a date property is about WHEN THE USER should do something → return null (user must specify)
- If a date property is about a FACTUAL date of the content (movie release, book published) → research it
- NEVER infer one date from another (don't use capture date, don't use release date as deadline)

RESPOND WITH JSON:
{{
    "property_name_1": "value",
    "property_name_2": 123,
    "property_name_3": null,
    ...
}}

Return ONLY valid JSON with property names as keys."""

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
    
    def select_best_database(
        self,
        user_data: Dict[str, Any],
        databases: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Use AI to select the most appropriate database.
        Returns detailed result with success/failure and reasoning.
        """
        client = self._get_client()
        
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
        
        prompt = f"""Select the most appropriate Notion database for this content.

RAW USER INPUT:
"{raw_input}"

ANALYZED CONTENT:
- Title: {title}
- Description: {description}
- Type: {content_type}
- Detailed Analysis: {detailed_analysis}

AVAILABLE DATABASES:
{json.dumps(db_list, indent=2)}

INSTRUCTIONS:
1. Analyze if ANY database is a good semantic fit
2. Consider: database title, property names matching the content
3. Be STRICT - if no database truly fits, say so
4. Consider the content type and what kind of database it belongs in

RESPOND WITH JSON:
{{
    "found_match": true/false,
    "selected_index": <number or null>,
    "confidence": 0.0-1.0,
    "reason": "detailed explanation of selection OR why no database fits"
}}

If confidence < 0.5 or no good fit, set found_match to false."""

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


# Singleton instance
ai_service = AIService()
