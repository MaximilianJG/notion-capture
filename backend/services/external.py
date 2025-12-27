"""
External Apps Service - Handles connections to external services (Google Calendar, etc.)
"""
import os
import pickle
import json
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


class ExternalAppsService:
    """Service for syncing entries to external applications"""
    
    _instance = None
    _credentials = None
    
    # Google OAuth configuration
    SCOPES = ['https://www.googleapis.com/auth/calendar']
    CLIENT_SECRETS_FILE = os.getenv("GOOGLE_CLIENT_SECRETS_FILE", "client_secret.json")
    TOKEN_FILE = "token.pickle"
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    # ==================== Google OAuth ====================
    
    def get_google_credentials(self) -> Optional[Credentials]:
        """Load or refresh Google OAuth credentials"""
        if self._credentials and self._credentials.valid:
            return self._credentials
        
        # Try to load from file
        if os.path.exists(self.TOKEN_FILE):
            try:
                with open(self.TOKEN_FILE, 'rb') as token:
                    self._credentials = pickle.load(token)
            except Exception as e:
                print(f"⚠️ Error loading token.pickle: {e}")
                self._credentials = None
                return None
        
        # Refresh if expired
        if self._credentials and self._credentials.expired and self._credentials.refresh_token:
            try:
                print("🔄 Refreshing Google credentials...")
                import socket
                old_timeout = socket.getdefaulttimeout()
                socket.setdefaulttimeout(10)
                try:
                    self._credentials.refresh(GoogleRequest())
                    with open(self.TOKEN_FILE, 'wb') as token:
                        pickle.dump(self._credentials, token)
                    print("✅ Google credentials refreshed")
                finally:
                    socket.setdefaulttimeout(old_timeout)
            except Exception as e:
                print(f"⚠️ Error refreshing credentials: {e}")
                self._credentials = None
                return None
        
        return self._credentials if self._credentials and self._credentials.valid else None
    
    def set_google_credentials(self, credentials: Credentials):
        """Save new Google credentials"""
        self._credentials = credentials
        with open(self.TOKEN_FILE, 'wb') as token:
            pickle.dump(credentials, token)
    
    def clear_google_credentials(self):
        """Clear Google credentials (logout)"""
        self._credentials = None
        if os.path.exists(self.TOKEN_FILE):
            os.remove(self.TOKEN_FILE)
    
    def get_google_auth_url(self) -> Optional[Dict[str, str]]:
        """Generate Google OAuth authorization URL"""
        if not os.path.exists(self.CLIENT_SECRETS_FILE):
            return None
        
        flow = Flow.from_client_secrets_file(
            self.CLIENT_SECRETS_FILE,
            scopes=self.SCOPES,
            redirect_uri="http://127.0.0.1:8000/google/auth/callback"
        )
        
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )
        
        # Store state for verification
        with open('oauth_state.pickle', 'wb') as f:
            pickle.dump(state, f)
        
        return {"auth_url": authorization_url, "state": state}
    
    def handle_google_callback(self, code: str, state: str) -> Optional[Credentials]:
        """Handle Google OAuth callback and exchange code for credentials"""
        # Verify state
        if os.path.exists('oauth_state.pickle'):
            with open('oauth_state.pickle', 'rb') as f:
                stored_state = pickle.load(f)
            if state != stored_state:
                raise ValueError("Invalid state parameter")
        
        flow = Flow.from_client_secrets_file(
            self.CLIENT_SECRETS_FILE,
            scopes=self.SCOPES,
            redirect_uri="http://127.0.0.1:8000/google/auth/callback"
        )
        
        flow.fetch_token(code=code)
        credentials = flow.credentials
        
        # Save credentials
        self.set_google_credentials(credentials)
        
        # Clean up state file
        if os.path.exists('oauth_state.pickle'):
            os.remove('oauth_state.pickle')
        
        return credentials
    
    def get_google_user_info(self) -> Optional[Dict[str, Any]]:
        """Get Google user information from credentials"""
        credentials = self.get_google_credentials()
        if not credentials or not credentials.valid:
            return None
        
        try:
            service = build('calendar', 'v3', credentials=credentials)
            calendar_list = service.calendarList().list(maxResults=1).execute()
            
            if calendar_list.get('items'):
                calendar_id = calendar_list['items'][0].get('id')
                if '@' in str(calendar_id):
                    return {
                        "email": calendar_id,
                        "google_user_id": calendar_id,
                        "name": calendar_id.split('@')[0]
                    }
        except Exception as e:
            print(f"❌ Error getting Google user info: {e}")
        
        return None
    
    def get_google_auth_status(self) -> Dict[str, Any]:
        """Get current Google authentication status"""
        credentials = self.get_google_credentials()
        email = None
        token_valid = False
        error = None
        
        if credentials:
            try:
                if credentials.valid:
                    token_valid = True
                    user_info = self.get_google_user_info()
                    if user_info:
                        email = user_info.get("email")
                else:
                    error = "Token expired or invalid"
            except Exception as e:
                error = f"Error checking credentials: {str(e)}"
        
        return {
            "connected": credentials is not None and token_valid,
            "email": email,
            "token_valid": token_valid,
            "error": error,
            "has_credentials": credentials is not None
        }
    
    # ==================== Google Calendar Sync ====================
    
    def sync_to_google_calendar(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sync an entry to Google Calendar.
        Only syncs entries with category 'event'.
        
        Returns: {success, event_id, event_link, error}
        """
        credentials = self.get_google_credentials()
        if not credentials or not credentials.valid:
            return {
                "success": False,
                "error": "Google Calendar not connected or credentials invalid"
            }
        
        category = entry.get("category", "")
        if category != "event":
            return {
                "success": False,
                "error": f"Cannot sync category '{category}' to Google Calendar. Only 'event' category is supported."
            }
        
        try:
            service = build('calendar', 'v3', credentials=credentials)
            
            # Parse dates
            start_time = entry.get("start_date") or entry.get("start_time")
            end_time = entry.get("end_date") or entry.get("end_time")
            
            # Get local timezone
            local_now = datetime.now().astimezone()
            local_tz = local_now.tzinfo
            
            # Parse datetime strings
            start_dt = self._parse_datetime(start_time, local_tz)
            end_dt = self._parse_datetime(end_time, local_tz)
            
            # Default times if not provided
            if not start_dt:
                start_dt = local_now.replace(hour=9, minute=0, second=0, microsecond=0)
            if not end_dt:
                end_dt = start_dt + timedelta(hours=1)
            
            # Convert to UTC for Google Calendar API
            start_utc = start_dt.astimezone(timezone.utc)
            end_utc = end_dt.astimezone(timezone.utc)
            
            # Get timezone name
            tz_name = self._get_timezone_name(local_tz, local_now)
            
            # Build event object
            event = {
                'summary': entry.get("title", "Untitled Event"),
                'description': entry.get("description", ""),
                'start': {
                    'dateTime': start_utc.isoformat().replace('+00:00', 'Z'),
                    'timeZone': tz_name,
                },
                'end': {
                    'dateTime': end_utc.isoformat().replace('+00:00', 'Z'),
                    'timeZone': tz_name,
                },
            }
            
            if entry.get("location"):
                event['location'] = entry["location"]
            
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
    
    def delete_google_calendar_event(self, event_id: str) -> Dict[str, Any]:
        """Delete a Google Calendar event"""
        credentials = self.get_google_credentials()
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
    
    def _parse_datetime(self, dt_str: str, local_tz) -> Optional[datetime]:
        """Parse datetime string, treating it as local time if no timezone"""
        if not dt_str:
            return None
        
        try:
            # Remove Z if present
            if dt_str.endswith('Z'):
                dt_str = dt_str[:-1]
            
            dt = datetime.fromisoformat(dt_str)
            
            # If no timezone info, assume local time
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=local_tz)
            
            return dt
        except Exception as e:
            print(f"⚠️ Date parse error: {e}")
            return None
    
    def _get_timezone_name(self, local_tz, local_now: datetime) -> str:
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
    
    # ==================== Future External Services ====================
    # Add more sync methods here as needed:
    # - sync_to_notion()
    # - sync_to_todoist()
    # - sync_to_trello()
    # - etc.


# Singleton instance
external_service = ExternalAppsService()

