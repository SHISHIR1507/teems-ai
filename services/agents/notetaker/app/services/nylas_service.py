"""
Nylas API service abstraction
"""
import requests
from typing import Dict, Any, Optional
from app.core.config import get_settings
import logging

logger = logging.getLogger(__name__)


class NylasService:
    """Service for interacting with Nylas API"""
    
    def __init__(self):
        settings = get_settings()
        self.api_key = settings.nylas_api_key
        self.base_url = settings.nylas_base_url
    
    def schedule_notetaker(
        self,
        meeting_link: str,
        start_time: str,
        name: str,
        meeting_settings: Optional[Dict[str, bool]] = None
    ) -> Dict[str, Any]:
        """
        Schedule a notetaker meeting with Nylas
        
        Args:
            meeting_link: Meeting URL (Zoom, Teams, etc.)
            start_time: ISO format datetime string
            name: Meeting name
            meeting_settings: Optional dict with transcription, summary, etc.
        
        Returns:
            Nylas API response
        
        Raises:
            Exception: If API call fails
        """
        if not meeting_settings:
            meeting_settings = {
                "transcription": True,
                "summary": True,
                "action_items": True,
                "audio_recording": True,
                "video_recording": True
            }
        
        payload = {
            "meeting_link": meeting_link,
            "name": name,
            "start_time": start_time,
            "meeting_settings": meeting_settings
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            logger.info(f"Scheduling notetaker meeting: {name} at {start_time}")
            response = requests.post(
                f"{self.base_url}/v3/notetakers",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code not in [200, 201, 202]:
                error_msg = f"Nylas API error {response.status_code}: {response.text}"
                logger.error(error_msg)
                raise Exception(error_msg)
            
            return response.json()
        
        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to connect to Nylas API: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)
    
    def fetch_media_url(self, url: str, timeout: int = 10) -> Optional[str]:
        """
        Fetch content from a media URL
        
        Args:
            url: Media URL from Nylas
            timeout: Request timeout in seconds
        
        Returns:
            Content as string, or None if failed
        """
        try:
            response = requests.get(url, timeout=timeout)
            if response.status_code == 200:
                return response.text
            else:
                logger.warning(f"Failed to fetch media URL {url}: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error fetching media URL {url}: {e}")
            return None
    
    def fetch_json_media_url(self, url: str, timeout: int = 10) -> Optional[Dict[str, Any]]:
        """
        Fetch JSON content from a media URL
        
        Args:
            url: Media URL from Nylas
            timeout: Request timeout in seconds
        
        Returns:
            Parsed JSON dict, or None if failed
        """
        try:
            response = requests.get(url, timeout=timeout)
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Failed to fetch JSON media URL {url}: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error fetching JSON media URL {url}: {e}")
            return None
    
    def join_meeting(
        self,
        meeting_link: str,
        join_time: str,
        name: str,
        meeting_settings: Optional[Dict[str, bool]] = None
    ) -> Dict[str, Any]:
        """
        Join a meeting via Nylas Notetaker API at a specific time
        
        Args:
            meeting_link: Meeting URL (Zoom, Teams, Google Meet, etc.)
            join_time: ISO format datetime string (exactly when to join)
            name: Name for the notetaker instance
            meeting_settings: Optional dict with transcription, summary, etc.
        
        Returns:
            Nylas API response with notetaker ID
        
        Raises:
            Exception: If API call fails
        """
        if not meeting_settings:
            meeting_settings = {
                "transcription": True,
                "summary": True,
                "action_items": True,
                "audio_recording": True,
                "video_recording": True
            }
        
        payload = {
            "meeting_link": meeting_link,
            "name": name,
            "join_time": join_time,  # Exactly when to join
            "meeting_settings": meeting_settings
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            logger.info(f"Joining meeting via Nylas: {name} at {join_time}")
            response = requests.post(
                f"{self.base_url}/v3/notetakers",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code not in [200, 201, 202]:
                error_msg = f"Nylas API error {response.status_code}: {response.text}"
                logger.error(error_msg)
                raise Exception(error_msg)
            
            result = response.json()
            logger.info(f"Successfully joined meeting, notetaker ID: {result.get('data', {}).get('id')}")
            return result
        
        except requests.exceptions.RequestException as e:
            error_msg = f"Failed to connect to Nylas API: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)
    
    def get_notetaker_status(self, notetaker_id: str) -> Optional[Dict[str, Any]]:
        """
        Get status of a notetaker instance
        
        Args:
            notetaker_id: Nylas notetaker ID
        
        Returns:
            Notetaker status dict, or None if failed
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.get(
                f"{self.base_url}/v3/notetakers/{notetaker_id}",
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Failed to get notetaker status {notetaker_id}: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error getting notetaker status: {e}")
            return None
    
    def cancel_notetaker(self, notetaker_id: str) -> bool:
        """
        Cancel a scheduled notetaker instance
        
        Args:
            notetaker_id: Nylas notetaker ID
        
        Returns:
            True if successful, False otherwise
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.delete(
                f"{self.base_url}/v3/notetakers/{notetaker_id}",
                headers=headers,
                timeout=30
            )
            
            if response.status_code in [200, 204]:
                logger.info(f"Successfully cancelled notetaker {notetaker_id}")
                return True
            else:
                logger.warning(f"Failed to cancel notetaker {notetaker_id}: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Error cancelling notetaker: {e}")
            return False


# Singleton instance
nylas_service = NylasService()
