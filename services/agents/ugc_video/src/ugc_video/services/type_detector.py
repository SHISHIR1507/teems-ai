from typing import Optional
from loguru import logger

from ..models.conversation import UGCType


class UGCTypeDetector:
    """Service for auto-detecting UGC video type based on uploaded files and message content."""

    # Keywords that indicate digital product
    DIGITAL_KEYWORDS = [
        "app", "application", "website", "web", "mobile", "laptop", "desktop",
        "screenshot", "screen", "interface", "ui", "ux", "software", "platform",
        "digital", "online", "webapp", "web app"
    ]

    # Keywords that indicate service
    SERVICE_KEYWORDS = [
        "service", "consulting", "consultation", "support", "help", "assistance",
        "coaching", "training", "workshop", "session", "meeting", "call",
        "therapy", "counseling", "advice", "guidance", "mentoring"
    ]

    @classmethod
    def detect_type(
        cls,
        message: str,
        has_person_image: bool,
        has_product_image: bool,
        has_screenshot: bool,
        has_logo: bool
    ) -> UGCType:
        """
        Auto-detect UGC type based on uploaded files and message content.
        
        Detection logic:
        1. Physical Product: Both person_image and product_image are uploaded
        2. Digital Product: person_image + screenshot(s), or message mentions digital keywords
        3. Service: Only person_image with service keywords, or logo provided
        
        Args:
            message: User's message text
            has_person_image: Whether person image was uploaded
            has_product_image: Whether product image was uploaded
            has_screenshot: Whether screenshot(s) were uploaded
            has_logo: Whether logo was uploaded
            
        Returns:
            Detected UGCType enum value
        """
        message_lower = message.lower() if message else ""
        
        # Physical Product: Both person and product images
        if has_person_image and has_product_image:
            logger.info("Detected UGC type: PHYSICAL_PRODUCT (person + product images)")
            return UGCType.PHYSICAL_PRODUCT
        
        # Digital Product: Person image + screenshot, or digital keywords in message
        if has_person_image and has_screenshot:
            logger.info("Detected UGC type: DIGITAL_PRODUCT (person + screenshot)")
            return UGCType.DIGITAL_PRODUCT
        
        if has_person_image and any(keyword in message_lower for keyword in cls.DIGITAL_KEYWORDS):
            logger.info("Detected UGC type: DIGITAL_PRODUCT (digital keywords in message)")
            return UGCType.DIGITAL_PRODUCT
        
        # Service: Only person image with service keywords, or logo provided
        if has_person_image and not has_product_image and not has_screenshot:
            if has_logo or any(keyword in message_lower for keyword in cls.SERVICE_KEYWORDS):
                logger.info("Detected UGC type: SERVICE (person image + service context)")
                return UGCType.SERVICE
        
        # Default to physical product if person image exists (fallback)
        if has_person_image:
            logger.info("Defaulting to UGC type: PHYSICAL_PRODUCT (fallback)")
            return UGCType.PHYSICAL_PRODUCT
        
        # If no person image, default to service (user might be describing a service)
        logger.info("Defaulting to UGC type: SERVICE (no images detected)")
        return UGCType.SERVICE

    @classmethod
    def detect_from_files(
        cls,
        message: str,
        person_image: Optional[bytes] = None,
        product_image: Optional[bytes] = None,
        screenshot: Optional[bytes] = None,
        logo: Optional[bytes] = None
    ) -> UGCType:
        """
        Convenience method to detect type from file contents.
        
        Args:
            message: User's message text
            person_image: Person image file content (optional)
            product_image: Product image file content (optional)
            screenshot: Screenshot file content (optional)
            logo: Logo file content (optional)
            
        Returns:
            Detected UGCType enum value
        """
        return cls.detect_type(
            message=message,
            has_person_image=person_image is not None,
            has_product_image=product_image is not None,
            has_screenshot=screenshot is not None,
            has_logo=logo is not None
        )

