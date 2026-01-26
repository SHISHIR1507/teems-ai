"""
Meeting platform detection service
"""
import re
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)


class MeetingDetectionService:
    """Service for detecting meeting platforms from URLs"""
    
    # Platform patterns
    PLATFORMS = {
        "zoom": [
            r"zoom\.us/j/([0-9]+)",
            r"zoom\.us/meeting/([0-9]+)",
            r"zoom\.us/webinar/([0-9]+)",
            r"us02web\.zoom\.us/j/([0-9]+)",
            r"us04web\.zoom\.us/j/([0-9]+)",
        ],
        "teams": [
            r"teams\.microsoft\.com/l/meetup-join/",
            r"teams\.live\.com/meet/",
        ],
        "google_meet": [
            r"meet\.google\.com/[a-z]{3}-[a-z]{4}-[a-z]{3}",
            r"meet\.google\.com/[a-z]+",
        ],
        "webex": [
            r"webex\.com/meet/",
            r".*\.webex\.com/.*",
        ],
        "gotomeeting": [
            r"gotomeeting\.com/join/",
            r"global\.gotomeeting\.com/join/",
        ],
    }
    
    @staticmethod
    def detect_platform(meeting_link: str) -> Optional[str]:
        """
        Detect meeting platform from URL
        
        Args:
            meeting_link: Meeting URL
        
        Returns:
            Platform name (zoom, teams, google_meet, etc.) or None
        """
        if not meeting_link:
            return None
        
        meeting_link_lower = meeting_link.lower()
        
        for platform, patterns in MeetingDetectionService.PLATFORMS.items():
            for pattern in patterns:
                if re.search(pattern, meeting_link_lower):
                    logger.info(f"Detected platform: {platform} for link: {meeting_link[:50]}...")
                    return platform
        
        logger.warning(f"Could not detect platform for link: {meeting_link[:50]}...")
        return "unknown"
    
    @staticmethod
    def extract_meeting_id(meeting_link: str, platform: Optional[str] = None) -> Optional[str]:
        """
        Extract meeting ID from URL
        
        Args:
            meeting_link: Meeting URL
            platform: Optional platform name (if known)
        
        Returns:
            Meeting ID or None
        """
        if not meeting_link:
            return None
        
        if not platform:
            platform = MeetingDetectionService.detect_platform(meeting_link)
        
        meeting_link_lower = meeting_link.lower()
        
        if platform == "zoom":
            # Extract Zoom meeting ID
            match = re.search(r"zoom\.us/j/([0-9]+)", meeting_link_lower)
            if match:
                return match.group(1)
            match = re.search(r"zoom\.us/meeting/([0-9]+)", meeting_link_lower)
            if match:
                return match.group(1)
        
        elif platform == "google_meet":
            # Extract Google Meet code
            match = re.search(r"meet\.google\.com/([a-z]{3}-[a-z]{4}-[a-z]{3})", meeting_link_lower)
            if match:
                return match.group(1)
        
        # For other platforms, return None (ID extraction not critical)
        return None
    
    @staticmethod
    def validate_meeting_link(meeting_link: str) -> Dict[str, any]:
        """
        Validate meeting link and return platform info
        
        Args:
            meeting_link: Meeting URL
        
        Returns:
            Dict with platform, meeting_id, and is_valid
        """
        if not meeting_link or not meeting_link.strip():
            return {
                "is_valid": False,
                "platform": None,
                "meeting_id": None,
                "error": "Empty meeting link"
            }
        
        platform = MeetingDetectionService.detect_platform(meeting_link)
        meeting_id = MeetingDetectionService.extract_meeting_id(meeting_link, platform)
        
        return {
            "is_valid": platform is not None,
            "platform": platform,
            "meeting_id": meeting_id,
            "error": None if platform else "Unknown meeting platform"
        }


# Singleton instance
meeting_detection_service = MeetingDetectionService()
