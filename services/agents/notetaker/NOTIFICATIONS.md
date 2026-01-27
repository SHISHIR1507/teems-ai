# Real-time Notifications for Notetaker Service

## Overview

The notetaker service publishes events to Redis pub/sub channels that are consumed by the existing realtime workflow service and forwarded to frontend clients via WebSocket.

## Architecture

```
Notetaker Service → Redis Pub/Sub → Realtime Service → WebSocket → Frontend
```

- **Notetaker Service**: Publishes events to Redis channels
- **Redis Pub/Sub**: Message broker for multi-instance support
- **Realtime Service**: Subscribes to channels and forwards to WebSocket clients
- **Frontend**: Connects to realtime service WebSocket and receives notifications

## Channel Naming

- Format: `notetaker:{tenant_id}`
- Tenant-wide notifications (all users in tenant receive events)
- Example: `notetaker:tenant-123`

## Event Types

### Calendar Sync Events

#### `CALENDAR_SYNC_STARTED`
```json
{
  "type": "CALENDAR_SYNC_STARTED",
  "tenant_id": "tenant-123",
  "user_id": "user-456",
  "timestamp": "2024-01-15T10:00:00Z"
}
```

#### `CALENDAR_SYNC_COMPLETED`
```json
{
  "type": "CALENDAR_SYNC_COMPLETED",
  "tenant_id": "tenant-123",
  "user_id": "user-456",
  "synced_count": 10,
  "events_with_meetings": 5,
  "timestamp": "2024-01-15T10:01:00Z"
}
```

#### `CALENDAR_SYNC_FAILED`
```json
{
  "type": "CALENDAR_SYNC_FAILED",
  "tenant_id": "tenant-123",
  "user_id": "user-456",
  "error": "Failed to get Google credentials",
  "timestamp": "2024-01-15T10:00:30Z"
}
```

### Meeting Join Events

#### `MEETING_JOIN_STARTED`
```json
{
  "type": "MEETING_JOIN_STARTED",
  "tenant_id": "tenant-123",
  "call_id": "call-789",
  "meeting_title": "Team Standup",
  "start_time": "2024-01-15T14:30:00Z",
  "timestamp": "2024-01-15T14:30:00Z"
}
```

#### `MEETING_JOIN_COMPLETED`
```json
{
  "type": "MEETING_JOIN_COMPLETED",
  "tenant_id": "tenant-123",
  "call_id": "call-789",
  "notetaker_id": "nylas-123",
  "meeting_title": "Team Standup",
  "timestamp": "2024-01-15T14:30:05Z"
}
```

#### `MEETING_JOIN_FAILED`
```json
{
  "type": "MEETING_JOIN_FAILED",
  "tenant_id": "tenant-123",
  "call_id": "call-789",
  "error": "Failed to get notetaker ID from Nylas",
  "timestamp": "2024-01-15T14:30:05Z"
}
```

### Meeting Processing Events

#### `MEETING_PROCESSING_STARTED`
```json
{
  "type": "MEETING_PROCESSING_STARTED",
  "tenant_id": "tenant-123",
  "call_id": "call-789",
  "meeting_title": "Team Standup",
  "timestamp": "2024-01-15T14:30:10Z"
}
```

#### `MEETING_PROCESSING_COMPLETED`
```json
{
  "type": "MEETING_PROCESSING_COMPLETED",
  "tenant_id": "tenant-123",
  "call_id": "call-789",
  "has_transcript": true,
  "has_summary": true,
  "has_action_items": true,
  "timestamp": "2024-01-15T14:35:00Z"
}
```

### Status Update Events

#### `CALL_STATUS_UPDATED`
```json
{
  "type": "CALL_STATUS_UPDATED",
  "tenant_id": "tenant-123",
  "call_id": "call-789",
  "status": "completed",
  "meeting_title": "Team Standup",
  "timestamp": "2024-01-15T14:35:00Z"
}
```

## Frontend Integration

### Connect to Realtime Service

```javascript
const ws = new WebSocket('wss://realtime-service.example.com/ws');

// Authenticate
ws.onopen = () => {
  // Send auth token (implementation depends on your auth flow)
};

// Subscribe to notetaker channel
ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  
  if (message.type === 'WELCOME') {
    // Subscribe to tenant channel
    ws.send(JSON.stringify({
      action: 'subscribe',
      channels: [`notetaker:${tenantId}`]
    }));
  }
  
  if (message.type === 'SUBSCRIBED') {
    console.log('Subscribed to notifications');
  }
  
  // Handle notifications
  if (message.type === 'CALENDAR_SYNC_STARTED') {
    // Show sync in progress
  }
  
  if (message.type === 'CALENDAR_SYNC_COMPLETED') {
    // Update UI with synced count
  }
  
  if (message.type === 'MEETING_JOIN_STARTED') {
    // Show meeting join in progress
  }
  
  if (message.type === 'MEETING_JOIN_COMPLETED') {
    // Show meeting joined successfully
  }
  
  if (message.type === 'MEETING_PROCESSING_COMPLETED') {
    // Enable Q&A, show transcript available
  }
};
```

## Configuration

### Environment Variables

```env
# Redis URL (optional - notifications disabled if not set)
REDIS_URL=redis://localhost:6379/0
```

### Graceful Degradation

- If `REDIS_URL` is not set, notifications are disabled
- Service continues to work normally
- Logs warnings when trying to publish without Redis
- No errors thrown - notifications are non-blocking

## Notification Points

1. **Calendar Sync** (`/v1/calendar/sync`):
   - Started: When sync begins
   - Completed: When sync finishes successfully
   - Failed: When sync encounters errors

2. **Meeting Join** (auto-join or manual):
   - Started: When join process begins
   - Completed: When Nylas successfully joins
   - Failed: When join fails

3. **Meeting Processing** (webhook):
   - Started: When webhook receives media ready event
   - Completed: When transcript/summary/action items are processed

4. **Status Updates**:
   - Published when call status changes (scheduled → processing → completed)

## Testing

### Test Redis Connection

```bash
# Check if Redis is accessible
redis-cli ping

# Subscribe to channel manually
redis-cli SUBSCRIBE "notetaker:your-tenant-id"
```

### Test Notifications

1. Trigger calendar sync: `POST /v1/calendar/sync`
2. Check Redis: Should see `CALENDAR_SYNC_STARTED` and `CALENDAR_SYNC_COMPLETED`
3. Connect frontend WebSocket to realtime service
4. Subscribe to `notetaker:{tenant_id}` channel
5. Verify notifications are received

## Error Handling

- All notification calls are non-blocking
- Errors in notification publishing are logged but don't affect main flow
- Redis connection failures are handled gracefully
- Service continues to work even if Redis is unavailable
