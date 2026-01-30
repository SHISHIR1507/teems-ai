"""
Avatar configuration and mapping
Maps avatar IDs to S3 URLs and custom ElevenLabs voice IDs
"""
import json
from pathlib import Path
from typing import Dict, Optional

# Load avatar mapping from JSON file
AVATARS_JSON_PATH = Path(__file__).parent.parent.parent / "avatars_mapping.json"

def load_avatar_mapping() -> Dict:
    """Load avatar mapping from JSON file"""
    try:
        with open(AVATARS_JSON_PATH, 'r') as f:
            data = json.load(f)
            return data.get('avatars', {})
    except Exception as e:
        print(f"Warning: Failed to load avatar mapping: {e}")
        return {}

# Load avatars at module import
AVATAR_REGISTRY = load_avatar_mapping()

def get_avatar_s3_url(avatar_id: int) -> Optional[str]:
    """Get S3 URL for avatar by ID"""
    avatar = AVATAR_REGISTRY.get(str(avatar_id))
    return avatar.get('s3_url') if avatar else None

def get_avatar_voice_id(avatar_id: int) -> Optional[str]:
    """Get custom voice ID for avatar by ID"""
    avatar = AVATAR_REGISTRY.get(str(avatar_id))
    return avatar.get('custom_voice_id') if avatar else None

def get_avatar_voice_name(avatar_id: int) -> Optional[str]:
    """Get voice name for avatar by ID"""
    avatar = AVATAR_REGISTRY.get(str(avatar_id))
    return avatar.get('voice_name') if avatar else None

def get_all_avatars() -> Dict:
    """Get all available avatars"""
    return AVATAR_REGISTRY

def avatar_exists(avatar_id: int) -> bool:
    """Check if avatar ID exists"""
    return str(avatar_id) in AVATAR_REGISTRY
