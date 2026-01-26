"""
Timezone management service
"""
import pytz
from datetime import datetime
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class TimezoneService:
    """Service for timezone conversions and management"""
    
    @staticmethod
    def validate_timezone(timezone_str: str) -> bool:
        """Validate if a timezone string is valid"""
        try:
            pytz.timezone(timezone_str)
            return True
        except pytz.exceptions.UnknownTimeZoneError:
            return False
    
    @staticmethod
    def get_timezone(timezone_str: str) -> pytz.BaseTzInfo:
        """Get timezone object from string"""
        try:
            return pytz.timezone(timezone_str)
        except pytz.exceptions.UnknownTimeZoneError:
            logger.warning(f"Invalid timezone: {timezone_str}, defaulting to UTC")
            return pytz.UTC
    
    @staticmethod
    def convert_to_utc(dt: datetime, from_timezone: str) -> datetime:
        """Convert datetime from user timezone to UTC"""
        if dt.tzinfo is None:
            # Assume naive datetime is in the specified timezone
            tz = TimezoneService.get_timezone(from_timezone)
            dt = tz.localize(dt)
        
        return dt.astimezone(pytz.UTC)
    
    @staticmethod
    def convert_from_utc(dt: datetime, to_timezone: str) -> datetime:
        """Convert datetime from UTC to user timezone"""
        if dt.tzinfo is None:
            # Assume naive datetime is UTC
            dt = pytz.UTC.localize(dt)
        
        tz = TimezoneService.get_timezone(to_timezone)
        return dt.astimezone(tz)
    
    @staticmethod
    def now_in_timezone(timezone_str: str) -> datetime:
        """Get current time in specified timezone"""
        tz = TimezoneService.get_timezone(timezone_str)
        return datetime.now(tz)
    
    @staticmethod
    def format_datetime_for_nylas(dt: datetime) -> str:
        """Format datetime as ISO string for Nylas API"""
        if dt.tzinfo is None:
            dt = pytz.UTC.localize(dt)
        return dt.isoformat()


# Singleton instance
timezone_service = TimezoneService()
