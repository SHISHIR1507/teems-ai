# Onboarding Service

FastAPI microservice that guides users through a 5-stage onboarding process using an LLM-powered chatbot. The service integrates with Brandfetch API, Agent Manager, and provides websocket notifications via Redis pubsub.

## Features

- **5-Stage Onboarding Flow**:
  1. Login/Signup (handled externally)
  2. Brand Discovery - Collect and fetch brand information via Brandfetch API
  3. Suggested Teammates - Help users select AI teammates/agents
  4. Connect Your World - Collect integration preferences
  5. Personalization - Set up notification preferences

- **LLM-Powered Chat**: Natural conversation flow powered by AIML API (OpenAI/Gemini models)
- **State Management**: Persistent onboarding state with conversation history
- **WebSocket Integration**: Real-time notifications via Redis pubsub (forwarded by realtime service)
- **API Integration**: Seamless integration with Brandfetch and Agent Manager services

## Quickstart

```bash
cd services/onboarding-service
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env .env.local  # fill values inside .env.local
uvicorn app.main:app --reload --port 8097
```

### Environment Variables

Update `.env`/`.env.local` with:

- `DATABASE_URL` – SQLAlchemy async connection string (e.g., `postgresql+asyncpg://user:pass@host:5432/db`)
- `REDIS_URL` – Redis connection URL for pubsub events
- `AIML_API_KEY` – AIML API key for LLM requests
- `AIML_BASE_URL` – AIML API endpoint (default: `https://api.aimlapi.com/v1`)
- `DEFAULT_LLM_MODEL` – LLM model to use (default: `openai/gpt-4o-mini`)
- `AUTH0_DOMAIN`, `AUTH0_AUDIENCE`, `AUTH0_ALGORITHM` – Auth0 configuration
- `BRANDFETCH_API_URL` – Internal Brandfetch service URL (default: `http://localhost:8095`)
- `AGENT_MANAGER_API_URL` – Internal Agent Manager service URL (default: `http://localhost:8000`)
- `ONBOARDING_CHANNEL_PREFIX` – Redis channel prefix for events (default: `onboarding`)

## API Endpoints

- `GET /health` – Health check endpoint
- `POST /chat` – Main chat endpoint for onboarding flow
  - **Request Body**:
    ```json
    {
      "message": "Hello, I'd like to get started",
      "conversation_id": "optional-uuid" // Optional, for resuming conversations
    }
    ```
  - **Response**:
    ```json
    {
      "message": "Assistant response",
      "conversation_id": "uuid",
      "current_stage": "brand_discovery",
      "stage_completed": false,
      "metadata": {
        "brand_domain": null,
        "selected_teammates_count": 0,
        "connected_integrations_count": 0
      }
    }
    ```

All endpoints require authentication via Bearer token (Auth0 JWT).

## WebSocket Events

The service publishes events to Redis channels that are forwarded via the realtime websocket service:

- **Channel**: `onboarding:{tenant_id}`
- **Event Types**:
  - `brandfetch.completed` – When brand information is fetched
  - `onboarding.completed` – When onboarding flow is complete

Frontend should connect to the realtime service websocket and subscribe to the appropriate channel.

## Onboarding Stages

### Stage 1: Login/Signup
Handled externally before onboarding service is accessed.

### Stage 2: Brand Discovery
- Chatbot asks for website URL
- Validates URL format
- Calls Brandfetch API if valid
- Publishes `brandfetch.completed` event to `onboarding:{tenant_id}` channel
- Advances to next stage on success
- **Note**: The frontend receives the event via websocket and can fetch brand details

### Stage 3: Suggested Teammates
- Chatbot introduces the teammate selection step
- Guides user through selecting teammates
- **Note**: Frontend handles fetching available agents, presenting them, and creating assignments
- Advances to next stage when user indicates readiness
- Publishes `stage.completed` event with `next_step: connect_world`

### Stage 4: Connect Your World
- Chatbot introduces integration connection step
- Guides user about connecting applications
- **Note**: Frontend handles integration connection UI and OAuth flows
- User can skip this step
- Advances to next stage when user indicates readiness
- Publishes `stage.completed` event with `next_step: personalization`

### Stage 5: Personalization
- Chatbot introduces notification preferences step
- Guides user through notification setup
- **Note**: Frontend handles notification preference selection and storage
- Advances to completion when user indicates readiness
- Publishes `onboarding.completed` event

## Database Models

- **OnboardingState**: Tracks user's onboarding progress
- **ConversationMessage**: Stores chat conversation history
- **UserIntegration**: Tracks user's connected integrations (for future use)

## Docker

```bash
docker build -t onboarding-service .
docker run --env-file .env -p 8097:8080 onboarding-service
```

## Deployment Notes

- Requires PostgreSQL database
- Requires Redis for pubsub events
- Needs access to Brandfetch API service
- Needs access to Agent Manager API service
- AIML API key required for LLM functionality
- Auth0 configuration required for authentication

## Integration Flow

```
Frontend → POST /chat → Onboarding Service
                         ↓
                    Stage Handler
                         ↓
              ┌──────────┼──────────┐
              ↓          ↓          ↓
        Brandfetch   LLM Service   Redis PubSub
        (Stage 2)    (All stages)   (Events)
              ↓          ↓          ↓
              └──────────┼──────────┘
                         ↓
              Realtime Service (WebSocket)
                         ↓
                    Frontend
                         ↓
              [Frontend handles data ops for stages 3-5]
```

## Important Notes

- **Stages 3-5**: The onboarding service only guides the conversation. The frontend is responsible for:
  - Stage 3: Fetching agents from Agent Manager API, displaying them, and creating assignments
  - Stage 4: Showing integration connection UI and handling OAuth flows
  - Stage 5: Displaying notification preference options and storing them
  
- **WebSocket Events**: The service publishes events to `onboarding:{tenant_id}` channel via Redis pubsub. Frontend should:
  - Connect to the realtime websocket service
  - Subscribe to `onboarding:{tenant_id}` channel
  - Listen for `brandfetch.completed`, `stage.completed`, and `onboarding.completed` events
  - React to events by showing appropriate UI or fetching data

