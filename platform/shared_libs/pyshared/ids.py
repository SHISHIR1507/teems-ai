"""
Helpers for resolving optional conversation/session IDs from the frontend.

When the frontend has no real ID yet, it may send placeholders (e.g. "string").
We treat those as "assign new" and return a new UUID. Non-placeholder values
are returned as-is so the client can continue an existing conversation.
"""
import uuid
from typing import Optional

# Placeholders that indicate "no real id, assign new"
_CONVERSATION_ID_PLACEHOLDERS = frozenset({"string", "optional-uuid", "uuid"})


def resolve_conversation_id(value: Optional[str]) -> str:
    """
    If value is None, empty, or a known placeholder, return a new UUID.
    Otherwise return value as-is (caller uses it to continue existing conversation).

    Use at request-handling boundaries before create/get_or_create when the
    client can send conversation_id or session_id. Ensure the resolved ID
    is returned in the response so the client can pass it on subsequent requests.
    """
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return str(uuid.uuid4())
    if isinstance(value, str) and value.strip().lower() in _CONVERSATION_ID_PLACEHOLDERS:
        return str(uuid.uuid4())
    return value
