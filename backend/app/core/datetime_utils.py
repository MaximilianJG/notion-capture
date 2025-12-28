"""
Datetime utilities for timezone-aware operations
"""
from datetime import datetime
from typing import Dict


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


def parse_datetime_string(dt_str: str, local_tz=None) -> datetime | None:
    """Parse datetime string, treating it as local time if no timezone"""
    if not dt_str:
        return None
    
    try:
        # Remove Z if present
        if dt_str.endswith('Z'):
            dt_str = dt_str[:-1]
        
        dt = datetime.fromisoformat(dt_str)
        
        # If no timezone info and we have a local tz, assume local time
        if dt.tzinfo is None and local_tz:
            dt = dt.replace(tzinfo=local_tz)
        
        return dt
    except Exception as e:
        print(f"⚠️ Date parse error: {e}")
        return None

