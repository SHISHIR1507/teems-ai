# Regenerate Button Implementation Guide

## Backend Changes

### New Parameter
- Added `regenerate: Optional[bool] = Form(False)` to `/v1/ugc/upload` endpoint
- When `regenerate=true`, the system will re-generate images using existing images from state

### New Response Field
- Added `show_regenerate_button: bool` to `ChatResponse`
- Frontend should show the "Regenerate" button when this is `true`

## Frontend Implementation

### 1. Show Regenerate Button
```javascript
// Show button when response indicates
if (response.show_regenerate_button) {
  // Display "Regenerate" button above/near text input
}

// Alternative: Check conversation state
if (response.conversation_state?.next_step === "regenerate_or_video") {
  // Display "Regenerate" button
}
```

### 2. Handle Button Click
```javascript
function handleRegenerateClick() {
  // Get user's new instructions from text input
  const message = textInput.value || "Generate more variations";
  
  // Send request with regenerate flag
  const formData = new FormData();
  formData.append('message', message);
  formData.append('regenerate', 'true');
  formData.append('conversation_id', conversationId);
  
  // Optional: Include avatar_id if user wants different avatar
  if (selectedAvatarId) {
    formData.append('avatar_id', selectedAvatarId);
  }
  
  fetch('/v1/ugc/upload', {
    method: 'POST',
    body: formData,
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });
}
```

### 3. UI/UX Recommendations

**Button Placement:**
- Show above or next to the text input
- Only visible when `show_regenerate_button === true`
- Hide when user is in earlier stages (brand sync, upload images)

**Button Text:**
- "Regenerate" or "Generate More"
- Could show count: "Regenerate (8 images so far)"

**User Flow:**
1. User generates initial 4 images
2. "Regenerate" button appears
3. User types new instructions: "try avatar 5" or "more gym-focused"
4. User clicks "Regenerate" button
5. System generates 4 MORE images (total 8)
6. Button remains visible for more regenerations

**Example Messages for Regeneration:**
- "try avatar 5"
- "more gym-focused"
- "different angles"
- "professional vibe"
- "with different product"
- Or just click without typing for same variations

## API Flow

### Normal Generation (First Time)
```
POST /v1/ugc/upload
- message: "generate images"
- person_image: [file]
- product_image: [file]
- regenerate: false (or omit)

Response:
- generated_images: [4 URLs]
- show_regenerate_button: true
- conversation_state.next_step: "regenerate_or_video"
```

### Regeneration (With Button)
```
POST /v1/ugc/upload
- message: "try avatar 5"
- regenerate: true
- avatar_id: 5
- conversation_id: "abc123"

Response:
- generated_images: [4 NEW URLs]
- show_regenerate_button: true
- conversation_state.generated_images: [8 total URLs]
```

### Normal Chat (No Generation)
```
POST /v1/ugc/upload
- message: "how many images do I have?"
- regenerate: false (or omit)
- conversation_id: "abc123"

Response:
- assistant_message: "You have 8 generated images!"
- generated_images: null
- show_regenerate_button: true (still shown)
```

## Benefits

✅ Clear UX - Button makes regeneration intent obvious
✅ No confusion - Agent won't accidentally trigger generation
✅ Agent can answer questions normally
✅ User controls when to regenerate
✅ Works with any message (avatar change, vibe change, etc.)
✅ Can build library of unlimited variations
