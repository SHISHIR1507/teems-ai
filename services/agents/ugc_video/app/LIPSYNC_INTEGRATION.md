# Lipsync Integration - Step 3 Added ✅

## What Changed

Added **Step 3: Lipsync** to the `/v1/ugc/script` endpoint to complete the video creation workflow.

## New 3-Agent Workflow

### Step 1: Script Generation (20% progress)
- Agent: `script_agent`
- Tool: "UGC Script Maker"
- Output: Dialogue + Video Script

### Step 2: Audio + Video Generation (50-70% progress)
- Agent: `audio_video_agent`
- Tools: 
  - "UGC Audio Generator" → Audio S3 URL
  - "Veo3.1 Image-to-Video Generator" → Video URL

### Step 3: Lipsync (85-100% progress) ⭐ NEW
- Agent: `lipsync_agent`
- Tool: "Lipsync Video Generator"
- Input: `audio_url` + `video_url`
- Output: `final_video_url` (lipsynced)

## Progress Tracking

```
25%  - Script generated
50%  - Audio generated
75%  - Video generated
100% - Lipsync complete (FINAL VIDEO)
```

## Response Changes

The endpoint now returns:
- `video_url`: The **final lipsynced video** (if lipsync succeeded)
- Falls back to raw video if lipsync fails
- `final_video_url` added to job completion notification

## Database Storage

New asset type stored:
```python
asset_type="final_video"
metadata={
    "duration": 8,
    "platform": platform,
    "lipsynced": True
}
```

## Real-time Notifications

New progress step:
```json
{
  "step": "lipsyncing",
  "progress": 85,
  "message": "Syncing audio with video (this may take 30-60 seconds)..."
}
```

## API Requirements

Make sure `LIPSYNC_API_KEY` is set in your `.env` file for the Sync.so API.

## Testing

```bash
POST /v1/ugc/script
{
  "ugc_image_path": "https://...",
  "product_name": "Skincare Serum",
  "avatar_id": 1,
  "conversation_id": "uuid",
  "tone": "energetic",
  "platform": "Instagram"
}
```

Expected flow:
1. Script generated ✓
2. Audio generated ✓
3. Video generated ✓
4. **Lipsync applied** ✓
5. Final video URL returned

## Error Handling

If lipsync fails:
- Returns the raw video URL (from Step 2)
- Progress shows 75% (video step)
- No final_video asset stored
