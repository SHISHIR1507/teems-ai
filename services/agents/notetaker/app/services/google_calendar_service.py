"""
Google Calendar service for OAuth and calendar sync
"""
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import pytz
import logging
from app.core.config import get_settings
from app.services.encryption_service import encryption_service
from app.services.timezone_service import timezone_service

logger = logging.getLogger(__name__)


class GoogleCalendarService:
    """Service for Google Calendar integration"""
    
    # Scopes required for calendar access
    SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
    
    def __init__(self):
        settings = get_settings()
        self.client_id = settings.google_client_id
        self.client_secret = settings.google_client_secret
        self.redirect_uri = settings.google_redirect_uri
    
    def get_oauth_flow(self) -> Flow:
        """Create OAuth flow for Google Calendar"""
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [self.redirect_uri]
                }
            },
            scopes=self.SCOPES,
            redirect_uri=self.redirect_uri
        )
        return flow
    
    def get_authorization_url(self, state: Optional[str] = None) -> str:
        """
        Get Google OAuth authorization URL
        
        Args:
            state: Optional state parameter for OAuth flow
        
        Returns:
            Authorization URL
        """
        flow = self.get_oauth_flow()
        if state:
            flow.state = state
        authorization_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'  # Force consent to get refresh token
        )
        return authorization_url
    
    def exchange_code_for_tokens(self, code: str) -> Dict[str, Any]:
        """
        Exchange authorization code for tokens
        
        Args:
            code: Authorization code from OAuth callback
        
        Returns:
            Dict with tokens and credentials
        """
        flow = self.get_oauth_flow()
        flow.fetch_token(code=code)
        credentials = flow.credentials
        
        return {
            "token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": credentials.scopes,
            "expiry": credentials.expiry.isoformat() if credentials.expiry else None
        }
    
    def get_credentials_from_encrypted(self, encrypted_token: str, encrypted_refresh: str) -> Optional[Credentials]:
        """
        Get Credentials object from encrypted tokens
        
        Args:
            encrypted_token: Encrypted OAuth token JSON
            encrypted_refresh: Encrypted refresh token
        
        Returns:
            Credentials object or None if failed
        """
        try:
            token_dict = encryption_service.decrypt_json(encrypted_token)
            refresh_token = encryption_service.decrypt(encrypted_refresh)
            
            token_dict["refresh_token"] = refresh_token
            
            credentials = Credentials.from_authorized_user_info(token_dict)
            
            # Refresh if expired
            if credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
            
            return credentials
        except Exception as e:
            logger.error(f"Error getting credentials from encrypted tokens: {e}")
            return None
    
    def encrypt_credentials(self, credentials: Credentials) -> Dict[str, str]:
        """
        Encrypt credentials for storage
        
        Args:
            credentials: Google Credentials object
        
        Returns:
            Dict with encrypted_token and encrypted_refresh_token
        """
        token_dict = {
            "token": credentials.token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": credentials.scopes,
            "expiry": credentials.expiry.isoformat() if credentials.expiry else None
        }
        
        encrypted_token = encryption_service.encrypt_json(token_dict)
        encrypted_refresh = encryption_service.encrypt(credentials.refresh_token) if credentials.refresh_token else ""
        
        return {
            "encrypted_token": encrypted_token,
            "encrypted_refresh_token": encrypted_refresh
        }
    
    def refresh_credentials(self, credentials: Credentials) -> Optional[Credentials]:
        """
        Refresh expired credentials
        
        Args:
            credentials: Google Credentials object
        
        Returns:
            Refreshed credentials or None if failed
        """
        try:
            if credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
                return credentials
            return credentials
        except Exception as e:
            logger.error(f"Error refreshing credentials: {e}")
            return None
    
    def get_calendar_service(self, credentials: Credentials):
        """Get Google Calendar API service"""
        try:
            return build('calendar', 'v3', credentials=credentials)
        except Exception as e:
            logger.error(f"Error building calendar service: {e}")
            return None
    
    def sync_calendar_events(
        self,
        credentials: Credentials,
        time_min: Optional[datetime] = None,
        time_max: Optional[datetime] = None,
        max_results: int = 250
    ) -> List[Dict[str, Any]]:
        """
        Sync calendar events from Google Calendar
        
        Args:
            credentials: Google Credentials
            time_min: Start time for events (default: now)
            time_max: End time for events (default: now + 7 days)
            max_results: Maximum number of results
        
        Returns:
            List of calendar events
        """
        try:
            # Refresh credentials if needed
            credentials = self.refresh_credentials(credentials)
            if not credentials:
                logger.error("Failed to refresh credentials")
                return []
            
            service = self.get_calendar_service(credentials)
            if not service:
                return []
            
            # Default time range
            if not time_min:
                time_min = datetime.now(pytz.UTC)
            if not time_max:
                time_max = time_min + timedelta(days=7)
            
            # Format times for API
            time_min_str = time_min.isoformat()
            time_max_str = time_max.isoformat()
            
            logger.info(f"Syncing calendar events from {time_min_str} to {time_max_str}")
            
            events_result = service.events().list(
                calendarId='primary',
                timeMin=time_min_str,
                timeMax=time_max_str,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            logger.info(f"Retrieved {len(events)} calendar events")
            
            return events
        
        except HttpError as e:
            logger.error(f"Google Calendar API error: {e}")
            return []
        except Exception as e:
            logger.error(f"Error syncing calendar events: {e}", exc_info=True)
            return []
    
    def extract_meeting_link_from_event(self, event: Dict[str, Any]) -> Optional[str]:
        """
        Extract meeting link from Google Calendar event
        
        Args:
            event: Google Calendar event dict
        
        Returns:
            Meeting link or None
        """
        # Check conferenceData (for Google Meet)
        conference_data = event.get('conferenceData', {})
        if conference_data:
            entry_points = conference_data.get('entryPoints', [])
            for entry_point in entry_points:
                if entry_point.get('entryPointType') == 'video':
                    return entry_point.get('uri')
        
        # Check location field
        location = event.get('location', '')
        if location:
            # Check if location contains a meeting link
            if any(platform in location.lower() for platform in ['zoom.us', 'teams.microsoft.com', 'meet.google.com', 'webex.com']):
                return location
        
        # Check description for meeting links
        description = event.get('description', '')
        if description:
            import re
            # Look for common meeting link patterns
            patterns = [
                r'https?://(?:[a-z]+\.)?zoom\.us/[^\s<>"]+',
                r'https?://teams\.microsoft\.com/[^\s<>"]+',
                r'https?://meet\.google\.com/[^\s<>"]+',
                r'https?://[^\s<>"]*webex\.com/[^\s<>"]+',
            ]
            for pattern in patterns:
                match = re.search(pattern, description, re.IGNORECASE)
                if match:
                    return match.group(0)
        
        return None
    
    def parse_event_datetime(self, event_datetime: Dict[str, Any]) -> Optional[datetime]:
        """
        Parse datetime from Google Calendar event
        
        Args:
            event_datetime: Event datetime dict (dateTime or date)
        
        Returns:
            Datetime object or None
        """
        try:
            if 'dateTime' in event_datetime:
                # Full datetime
                dt_str = event_datetime['dateTime']
                dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
                return dt
            elif 'date' in event_datetime:
                # All-day event
                date_str = event_datetime['date']
                dt = datetime.fromisoformat(date_str)
                # Set to start of day in UTC
                return pytz.UTC.localize(dt)
            return None
        except Exception as e:
            logger.error(f"Error parsing event datetime: {e}")
            return None


# Singleton instance
google_calendar_service = GoogleCalendarService()
