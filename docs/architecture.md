# Architecture

## Platform intent

Sonic Calling is designed as a **developer platform starter for realtime voice agents**, not as a one-screen toy app. The repo is intentionally split into:

- backend orchestration primitives
- a Twilio-facing telephony edge
- an OpenAI Realtime transport layer
- a browser operator cockpit
- local verification and smoke automation

## High-level flow

```text
Operator console
    -> session plan / client secret / simulator
FastAPI control plane
    -> session store
    -> compliance policy
    -> realtime orchestrator
    -> OpenAI transport
Twilio Voice
    -> POST /twilio/voice/{session_id}
    -> WebSocket /twilio/media-stream/{session_id}
OpenAI Realtime
    -> session.update
    -> input audio append
    -> output audio delta
```

## Main backend responsibilities

### `config.py`

Holds deploy-time configuration for:

- OpenAI Realtime endpoints and audio formats
- transcription model
- turn detection strategy
- Twilio account metadata
- quiet-hours policy

### `realtime.py`

Owns the **agent runtime blueprint**:

- disclosure-aware opening lines
- current Realtime session shape
- audio format selection
- VAD / semantic turn-detection configuration
- tool declarations
- local simulator turn logic

### `openai_transport.py`

Owns **direct OpenAI transport** concerns:

- building the Realtime WebSocket URL
- auth headers
- opening a live Realtime socket
- minting short-lived client secrets via REST

### `realtime_bridge.py`

Owns the **Twilio <-> OpenAI event bridge**:

- normalize Twilio websocket frames
- maintain per-session runtime status
- forward inbound Twilio media to `input_audio_buffer.append`
- return assistant audio back to Twilio as `media`
- send `mark` and `clear` control events
- store event timelines for operator inspection

### `store.py`

Provides a lightweight in-memory session ledger with:

- session creation
- session retrieval and listing
- event retention
- runtime telemetry persistence

## Realtime session contract

The generated session template is shaped around current OpenAI Realtime capabilities:

- `output_modalities: ["audio"]`
- `audio.input.format = g711_ulaw`
- `audio.output.format = g711_ulaw`
- input transcription via `gpt-4o-mini-transcribe`
- configurable server VAD or semantic VAD
- tool declarations with `tool_choice = auto`

Using `g711_ulaw` on both sides avoids an extra transcoding layer when the caller audio arrives from Twilio Media Streams.

## Twilio bridge lifecycle

### 1. Session creation

The operator starts a session or requests a client secret. Sonic Calling allocates a session ID and stores:

- contact profile
- agent profile
- websocket path
- compliance state
- runtime defaults

### 2. Twilio voice webhook

`POST /twilio/voice/{session_id}` returns TwiML that:

- announces the disclosure-aware opener
- opens `<Connect><Stream>`
- attaches custom parameters

### 3. Twilio media websocket

Twilio sends websocket events such as:

- `connected`
- `start`
- `media`
- `dtmf`
- `mark`
- `stop`

The bridge records those into the session timeline and extracts:

- `streamSid`
- `callSid`
- media payload characteristics

### 4. OpenAI live bridge

If `OPENAI_API_KEY` is configured:

- Sonic Calling opens a server-side Realtime WebSocket
- sends `session.update`
- forwards incoming Twilio media payloads as `input_audio_buffer.append`
- listens for model events such as `response.created`, transcript events, function-call events, and `response.output_audio.delta`
- forwards assistant audio back to Twilio

If no key is configured:

- Sonic Calling stays in **simulator-only mode**
- the operator cockpit remains usable
- event shapes are still normalized and observable

## Operator cockpit

The frontend is meant to feel like a compact operations console rather than a CRUD admin screen. It exposes:

- runtime readiness cards
- contact workspace
- agent persona selection
- realtime simulator
- client-secret panel
- bridge telemetry
- event timeline
- session ledger

## Verification model

The repo validates three layers:

### 1. Contract tests

- dashboard summary structure
- runtime health
- session template format
- client-secret preview behavior
- ledger behavior
- bridge event normalization

### 2. Production web build

- TypeScript compilation
- Vite build output
- ESLint on the frontend

### 3. End-to-end smoke

- launch local API + web app
- click through the operator cockpit
- start simulator
- submit a caller turn
- capture a screenshot artifact

## Remaining go-live work

This starter is much closer to a real platform now, but production deployment still requires:

- public HTTPS + WSS hosting
- secure secret management
- Twilio phone-number and webhook provisioning
- per-region calling-law review
- durable storage instead of in-memory sessions
- business tool execution behind the declared tool names
