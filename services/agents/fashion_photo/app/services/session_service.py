from typing import Dict

# Session State
# { session_id: { 
#     "stage": "AVATAR_SELECTION", # AVATAR_SELECTION, APPAREL_UPLOAD, SCENE_SELECTION, GENERATION
#     "avatars": [], 
#     "apparel": [], 
#     "generated": [], 
#     "history": [] 
#   } 
# }
SESSIONS: Dict[str, Dict] = {}

def get_or_create_session(session_id: str) -> Dict:
    """Get existing session or create a new one."""
    if session_id not in SESSIONS:
        SESSIONS[session_id] = {
            "stage": "AVATAR_SELECTION",
            "avatars": [],
            "apparel": [],
            "generated": [],
            "history": []
        }
    return SESSIONS[session_id]

def update_session_history(session: Dict, user_message: str, agent_message: str):
    """Update session history with user and agent messages."""
    session["history"].append({"role": "User", "content": user_message})
    session["history"].append({"role": "Agent", "content": agent_message})
