# Architecture

## Platform intent

Sonic Calling is designed as a **developer platform starter for realtime voice agents**, not as a one-screen toy app. The repo is intentionally split into:

- backend orchestration primitives
- a BYO provider vault
- a tool execution mesh
- a Twilio-facing telephony edge
- an OpenAI Realtime transport layer
- a browser operator cockpit
- local verification and smoke automation

## High-level flow

```text
Operator console
    -> runtime config / provider vault / tool mesh
    -> session plan / client secret / simulator
FastAPI control plane
    -> session store
    -> compliance policy
    -> runtime config store
    -> tool registry
    -> realtime orchestrator
    -> OpenAI transport
Twilio Voice
    -> POST /twilio/voice/{session_id}
    -> WebSocket /twilio/media-stream/{session_id}
OpenAI Realtime
    -> session.update
    -> input audio append
    -> response.function_call_arguments.done
    -> function_call_output
    -> response.create
```

## Main backend responsibilities

### `config.py`

Holds deploy-time configuration for:

- OpenAI Realtime endpoints and audio formats
- transcription model
- turn detection strategy
- Twilio account metadata
- quiet-hours policy

### `runtime_config.py`

Owns the **bring-your-own API vault**:

- environment-managed provider seeding
- vault-managed provider creation
- active profile selection per surface
- readiness evaluation
- masked secret projection

### `tool_registry.py`

Owns the **tool mesh**:

- built-in integration catalog
- custom webhook integrations
- tool-to-function mapping
- execution history
- simulator-safe fallback behavior
- runtime auth attachment for outbound tool calls

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
- per-profile credential overrides
- opening a live Realtime socket
- minting short-lived client secrets via REST

### `realtime_bridge.py`

Owns the **Twilio <-> OpenAI event bridge**:

- normalize Twilio websocket frames
- maintain per-session runtime status
- forward inbound Twilio media to `input_audio_buffer.append`
- return assistant audio back to Twilio as `media`
- handle `mark` and `clear` control events
- execute live function-call outputs
- write tool results back into the Realtime conversation via `conversation.item.create` and `response.create`
- store event timelines for operator inspection

### `store.py`

Provides a lightweight in-memory session ledger with:

- session creation
- session retrieval and listing
- provider profile persistence per session
- tool execution retention
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

## Tool execution model

### Simulator path

When an operator submits a caller utterance through `/api/sessions/{session_id}/respond`:

1. `RealtimeOrchestrator.next_turn()` classifies the utterance
2. the reply includes a `tool_suggestion`
3. `ToolRegistry.execute()` runs the mapped integration
4. the ledger stores the execution record and summary
5. the UI surfaces the result immediately

### Live Realtime path

When OpenAI emits `response.function_call_arguments.done`:

1. the bridge parses the JSON arguments
2. `ToolRegistry.execute_async()` runs the mapped integration
3. the bridge records the execution in the session ledger
4. the bridge sends `conversation.item.create` with `function_call_output`
5. the bridge sends `response.create` so the model can continue the conversation using the tool result

## Twilio bridge lifecycle

### 1. Session creation

The operator starts a session or requests a client secret. Sonic Calling allocates a session ID and stores:

- contact profile
- agent profile
- active realtime profile ID
- active telephony profile ID
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

If a ready OpenAI Realtime profile is active:

- Sonic Calling opens a server-side Realtime WebSocket
- sends `session.update`
- forwards incoming Twilio media payloads as `input_audio_buffer.append`
- listens for model events such as `response.created`, transcript events, function-call events, and `response.output_audio.delta`
- forwards assistant audio back to Twilio
- converts tool results into `function_call_output` conversation items

If no ready profile is active:

- Sonic Calling stays in **simulator-only mode**
- the operator cockpit remains usable
- event shapes are still normalized and observable

## Operator cockpit

The frontend is meant to feel like a compact operations console rather than a CRUD admin screen. It exposes:

- runtime readiness cards
- provider vault panels
- tool mesh panels
- contact workspace
- agent persona selection
- realtime simulator
- client-secret panel
- bridge telemetry
- event timeline
- session ledger
- global tool history

## Verification model

The repo validates four layers:

### 1. Contract tests

- dashboard summary structure
- runtime health
- runtime config endpoints
- tool execution endpoints
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
- verify the advanced console surfaces
- capture a screenshot artifact

### 4. Documentation parity

- README updated for the BYO vault and tool mesh
- architecture notes aligned to the latest OpenAI/Twilio flow
- audit notes updated with current test counts

## Remaining go-live work

This starter is much closer to a real platform now, but production deployment still requires:

- public HTTPS + WSS hosting
- secure secret management beyond in-memory state
- Twilio phone-number and webhook provisioning
- per-region calling-law review
- durable storage instead of in-memory sessions
- production CRM / booking / webhook endpoints behind the tool mesh
