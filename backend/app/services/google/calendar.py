"""
Google Calendar operations - Stateless
"""
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .auth import build_credentials_from_tokens
from app.core.datetime_utils import parse_datetime_string


def _get_timezone_name(local_tz, local_now: datetime) -> str:
    """Get timezone name for Google Calendar API"""
    tz_name = str(local_tz)
    
    if hasattr(local_tz, 'zone'):
        tz_name = local_tz.zone
    elif '+' in tz_name or '-' in tz_name:
        # Fallback based on offset
        offset_hours = local_now.utcoffset().total_seconds() / 3600
        if offset_hours == 0:
            tz_name = "UTC"
        elif offset_hours == 1:
            tz_name = "Europe/Berlin"
        else:
            tz_name = "UTC"
    
    return tz_name


def create_calendar_event(
    tokens: Dict[str, Any],
    event_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Create a Google Calendar event.
    
    Args:
        tokens: Google OAuth tokens from frontend
        event_data: Event data with title, description, start_time, end_time, location
    
    Returns: {success, calendar_event_id, calendar_link, error}
    """
    credentials = build_credentials_from_tokens(tokens)
    if not credentials or not credentials.valid:
        return {
            "success": False,
            "error": "Google Calendar not connected or credentials invalid"
        }
    
    category = event_data.get("category", "")
    if category != "event":
        return {
            "success": False,
            "error": f"Cannot sync category '{category}' to Google Calendar. Only 'event' category is supported."
        }
    
    try:
        service = build('calendar', 'v3', credentials=credentials)
        
        # Parse dates
        start_time = event_data.get("start_date") or event_data.get("start_time")
        end_time = event_data.get("end_date") or event_data.get("end_time")
        
        # Get local timezone
        local_now = datetime.now().astimezone()
        local_tz = local_now.tzinfo
        
        # Parse datetime strings
        start_dt = parse_datetime_string(start_time, local_tz)
        end_dt = parse_datetime_string(end_time, local_tz)
        
        # Default times if not provided
        if not start_dt:
            start_dt = local_now.replace(hour=9, minute=0, second=0, microsecond=0)
        if not end_dt:
            end_dt = start_dt + timedelta(hours=1)
        
        # Convert to UTC for Google Calendar API
        start_utc = start_dt.astimezone(timezone.utc)
        end_utc = end_dt.astimezone(timezone.utc)
        
        # Get timezone name
        tz_name = _get_timezone_name(local_tz, local_now)
        
        # Build event object
        event = {
            'summary': event_data.get("title", "Untitled Event"),
            'description': event_data.get("description", ""),
            'start': {
                'dateTime': start_utc.isoformat().replace('+00:00', 'Z'),
                'timeZone': tz_name,
            },
            'end': {
                'dateTime': end_utc.isoformat().replace('+00:00', 'Z'),
                'timeZone': tz_name,
            },
        }
        
        if event_data.get("location"):
            event['location'] = event_data["location"]
        
        print(f"📅 Creating Google Calendar event: {event['summary']}")
        print(f"   Start: {start_dt.isoformat()}")
        print(f"   End: {end_dt.isoformat()}")
        
        # Create the event
        created_event = service.events().insert(calendarId='primary', body=event).execute()
        
        print(f"✅ Google Calendar event created: {created_event.get('id')}")
        
        return {
            "success": True,
            "calendar_event_id": created_event.get('id'),
            "calendar_link": created_event.get('htmlLink'),
            "event_start": str(created_event.get('start')),
            "event_end": str(created_event.get('end')),
        }
        
    except HttpError as e:
        error_msg = f"Google Calendar API Error: {e.resp.status}"
        print(f"❌ {error_msg}")
        return {"success": False, "error": error_msg}
    except Exception as e:
        error_msg = f"Error creating calendar event: {str(e)}"
        print(f"❌ {error_msg}")
        return {"success": False, "error": error_msg}


def delete_calendar_event(
    tokens: Dict[str, Any],
    event_id: str
) -> Dict[str, Any]:
    """Delete a Google Calendar event"""
    credentials = build_credentials_from_tokens(tokens)
    if not credentials or not credentials.valid:
        return {
            "success": False,
            "error": "Google Calendar not connected"
        }
    
    try:
        service = build('calendar', 'v3', credentials=credentials)
        service.events().delete(calendarId='primary', eventId=event_id).execute()
        
        print(f"✅ Deleted Google Calendar event: {event_id}")
        return {"success": True, "event_id": event_id}
        
    except HttpError as e:
        return {"success": False, "error": f"API Error: {e.resp.status}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

