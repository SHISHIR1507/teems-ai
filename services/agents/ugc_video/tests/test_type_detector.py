"""
Unit tests for UGC type detection
"""
import pytest
from ugc_video.services.type_detector import UGCTypeDetector
from ugc_video.models.conversation import UGCType


def test_detect_physical_product():
    """Test detection of physical product type"""
    ugc_type = UGCTypeDetector.detect_type(
        message="Show me with this product",
        has_person_image=True,
        has_product_image=True,
        has_screenshot=False,
        has_logo=False
    )
    assert ugc_type == UGCType.PHYSICAL_PRODUCT


def test_detect_digital_product_with_screenshot():
    """Test detection of digital product with screenshot"""
    ugc_type = UGCTypeDetector.detect_type(
        message="Show me with this app",
        has_person_image=True,
        has_product_image=False,
        has_screenshot=True,
        has_logo=False
    )
    assert ugc_type == UGCType.DIGITAL_PRODUCT


def test_detect_digital_product_with_keywords():
    """Test detection of digital product with keywords"""
    ugc_type = UGCTypeDetector.detect_type(
        message="Show me using this mobile app",
        has_person_image=True,
        has_product_image=False,
        has_screenshot=False,
        has_logo=False
    )
    assert ugc_type == UGCType.DIGITAL_PRODUCT


def test_detect_service_with_logo():
    """Test detection of service with logo"""
    ugc_type = UGCTypeDetector.detect_type(
        message="Talk about our service",
        has_person_image=True,
        has_product_image=False,
        has_screenshot=False,
        has_logo=True
    )
    assert ugc_type == UGCType.SERVICE


def test_detect_service_with_keywords():
    """Test detection of service with keywords"""
    ugc_type = UGCTypeDetector.detect_type(
        message="I want to promote our consulting service",
        has_person_image=True,
        has_product_image=False,
        has_screenshot=False,
        has_logo=False
    )
    assert ugc_type == UGCType.SERVICE


def test_detect_from_files():
    """Test detection from file contents"""
    person_bytes = b"fake_image_data"
    product_bytes = b"fake_product_data"
    
    ugc_type = UGCTypeDetector.detect_from_files(
        message="Show product",
        person_image=person_bytes,
        product_image=product_bytes,
        screenshot=None,
        logo=None
    )
    assert ugc_type == UGCType.PHYSICAL_PRODUCT

