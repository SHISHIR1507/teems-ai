# Script Endpoint Update - Simplified Request

## Summary
Updated `/v1/ugc/script` endpoint to automatically retrieve `product_name` and `avatar_id` from conversation context, requiring only `ugc_image_path` and `conversation_id`.

## Changes Made

### 1. ScriptRequest Schema (`models/schemas.py`)
**Before:**
- `product_name`: Required field
- `avatar_id`: Required field (default: 1)
- `conversation_id`: Optional field

**After:**
- `product_name`: Optional (retrieved from conversation if not provided)
- `avatar_id`: Optional (retrieved from conversation state if not provided)
- `conversation_id`: **Required** (needed to retrieve context)
- `tone`: Optional (default: "energetic and authentic")
- `platform`: Optional (default: "Instagram")

### 2. Script Endpoint Logic (`api/routes/ugc.py`)

**New Retrieval Logic:**
```python
# Get conversation state
conversation_state = await db_helpers.get_conversation_state(
    session, conversation_id, tenant_id
)

# Retrieve product_name from conversation if not in request
product_name = request.product_name or conversation.product_name

# Retrieve avatar_id from conversation state if not in request
avatar_id = request.avatar_id or conversation_state.get('avatar_id')

# Use defaults
tone = request.tone or "energetic and authentic"
platform = request.platform or "Instagram"
```

**Validation:**
- Validates that `product_name` exists (from request or conversation)
- Validates that `avatar_id` exists (from request or conversation state)
- Returns clear error messages if required data is missing

### 3. ConversationState Schema (`models/schemas.py`)
Added `product_name` field to track product name in conversation state.

### 4. Database Helpers (`services/db_helpers.py`)
- Added `product_name` to conversation state dictionary
- Added `has_product_name` boolean flag
- Retrieves `product_name` from `conversation.product_name`

## API Usage

### Minimal Request (Recommended)
```json
{
  "ugc_image_path": "https://s3.../generated_image_1.png",
  "conversation_id": "uuid-here"
}
```

**Requirements:**
- Brand must be synced (includes product_name)
- Avatar must be selected in conversation

### Full Request (Override)
```json
{
  "ugc_image_path": "https://s3.../generated_image_1.png",
  "conversation_id": "uuid-here",
  "product_name": "Custom Product Name",
  "avatar_id": 2,
  "tone": "professional and calm",
  "platform": "TikTok"
}
```

## Data Flow

1. **Brand Sync** → Stores `product_name` in `conversation.product_name`
2. **Avatar Selection** → Stores `avatar_id` in conversation assets
3. **Script Request** → Retrieves both from conversation automatically

## Error Handling

**Missing Product Name:**
```json
{
  "error": "Product name required",
  "detail": "Product name must be provided in request or synced via brand sync",
  "status_code": 400
}
```

**Missing Avatar ID:**
```json
{
  "error": "Avatar ID required",
  "detail": "Avatar ID must be provided in request or selected in conversation",
  "status_code": 400
}
```

## Benefits

✅ Simpler API calls - only 2 required fields
✅ Automatic context retrieval from conversation
✅ Maintains backward compatibility (can still override)
✅ Clear validation and error messages
✅ Defaults for tone and platform
