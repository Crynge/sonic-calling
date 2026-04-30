# Architecture

## Platform intent

Sonic Calling is shaped as a **developer platform starter** for realtime voice agents, not just a single-call demo. The repo is structured to feel like a minimal version of a product platform:

- backend primitives
- frontend control plane
- telephony entry points
- agent configuration
- local verification workflow

## Realtime call path

### 1. Session planning

The operator chooses:

- a contact persona
- an agent profile
- a use case such as reminder, qualification, or concierge routing

The backend returns:

- a compliance evaluation
- the opening line
- the websocket path for Twilio streaming
- the OpenAI Realtime session template

### 2. Twilio voice entry

`POST /twilio/voice/{session_id}` returns TwiML that:

- announces the opening line
- opens a bidirectional `<Connect><Stream>`
- passes custom parameters such as `session_id` and `agent_name`

### 3. Media stream bridge

`/twilio/media-stream/{session_id}` is the telephony edge:

- Twilio sends `connected`, `start`, `media`, `dtmf`, and `stop` events
- the bridge normalizes incoming events
- production deployments can forward audio frames to OpenAI Realtime over WebSocket

This repo ships the normalized event path and session blueprint so the integration surface is explicit and testable.

### 4. OpenAI Realtime session

The `RealtimeOrchestrator` creates a session template that includes:

- the realtime model
- output voice
- VAD configuration
- tool definitions for business workflows
- concise voice-agent instructions

### 5. Tool execution

The example tools are modeled as platform actions:

- `lookup_contact`
- `book_callback`
- `create_crm_note`
- `escalate_human`
- `reschedule_appointment`
- `confirm_booking`
- `send_sms_summary`

## Frontend

The dashboard is designed as a command-center style product surface rather than a generic CRUD admin panel. It focuses on:

- platform metrics
- contact selection
- agent profile context
- simulator transcript
- realtime trace visibility
- compliance reasoning

## Verification model

Local verification covers:

- API correctness
- frontend build correctness
- simulator interaction
- smoke-tested UI rendering
- Twilio webhook generation

Live PSTN behavior remains deploy-time work because it requires external accounts, public HTTPS/WSS endpoints, and real telephony credentials.
