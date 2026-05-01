# Sonic Calling

A developer-first realtime voice platform for building AI phone agents with **OpenAI Realtime**, **Twilio telephony**, a **bring-your-own API vault**, and a **tool execution mesh**.

Sonic Calling is intentionally shaped more like a **VideoSDK-style developer platform** than a one-off bot demo. The repo now includes:

- a richer operator cockpit
- a masked BYO provider vault for OpenAI, Twilio, and sidecar tooling profiles
- a live tool mesh for CRM, scheduling, messaging, handoff, and custom webhook flows
- a session ledger API with tool execution history
- OpenAI Realtime session templating aligned to current audio and function-calling flows
- Twilio bidirectional Media Streams wiring
- realtime client-secret minting
- live bridge telemetry and event timelines
- compliance guardrails
- simulator and smoke-tested local workflow

## What is included

- **Realtime voice runtime:** OpenAI Realtime session templates with tool declarations, transcription settings, turn detection, noise reduction, audio format controls, and output voice tuning
- **BYO provider vault:** active profile selection for realtime and telephony surfaces, masked secret display, readiness notes, and environment-vs-vault visibility
- **Tool mesh:** mapped business functions for `lookup_contact`, `book_callback`, `reschedule_appointment`, `create_crm_note`, `send_sms_summary`, `escalate_human`, and custom webhooks
- **Telephony edge:** Twilio `<Connect><Stream>` webhook responses plus a media-stream bridge that can forward `g711_ulaw` audio directly to OpenAI Realtime
- **Operator cockpit:** React dashboard for contact selection, agent personas, provider profiles, tool integrations, session planning, runtime readiness, event timeline inspection, bridge telemetry, and simulator turns
- **Session ledger:** API and UI surfaces for reviewing tracked sessions, stream state, event counts, transcripts, function-call outputs, and last tool activity
- **Browser-client path:** Realtime client-secret endpoint for browser or WebRTC-style flows using short-lived credentials
- **Compliance layer:** quiet-hours gating, DNC/revoked-consent blocking, disclosure checks, opt-out handling, and risky-claim detection

## Repo structure

```text
apps/
|-- api/
|   |-- app/
|   |   |-- services/
|   |   |   |-- compliance.py
|   |   |   |-- openai_transport.py
|   |   |   |-- realtime.py
|   |   |   |-- realtime_bridge.py
|   |   |   |-- runtime_config.py
|   |   |   |-- store.py
|   |   |   |-- tool_registry.py
|   |   |   `-- twilio_adapter.py
|   |   |-- config.py
|   |   |-- data.py
|   |   |-- main.py
|   |   `-- schemas.py
|   `-- requirements.txt
`-- web/
    `-- src/
        |-- App.tsx
        |-- index.css
        `-- main.tsx
docs/
|-- architecture.md
`-- audit.md
tests/
|-- test_api.py
|-- test_bridge.py
|-- test_realtime.py
|-- web_smoke.py
`-- artifacts/
```

## Core capabilities

### 1. Realtime session planning

`POST /api/session-plan`

Returns:

- selected contact
- selected agent profile
- compliance evaluation
- disclosure-aware opening line
- Twilio websocket path
- chosen Realtime model
- active BYO provider notes

### 2. Provider vault

- `GET /api/runtime/config`
- `POST /api/runtime/providers`
- `POST /api/runtime/providers/{surface}/select`

The runtime vault tracks:

- active realtime and telephony profiles
- masked secret state
- environment-managed vs vault-managed auth source
- readiness notes
- model and endpoint metadata

### 3. Tool mesh

- `GET /api/tools`
- `GET /api/tools/executions`
- `POST /api/tools`
- `POST /api/tools/{tool_id}/execute`

The tool mesh supports:

- simulator-safe built-ins
- webhook-backed custom integrations
- auth-profile attachment for outbound tool calls
- automatic execution from simulator turns
- live execution from OpenAI `response.function_call_arguments.done`

### 4. Session ledger

- `POST /api/sessions`
- `GET /api/sessions`
- `GET /api/sessions/{session_id}`
- `POST /api/sessions/{session_id}/respond`

The ledger tracks:

- conversation turns
- state transitions
- runtime mode and bridge status
- selected provider and telephony profile IDs
- Twilio/OpenAI event counts
- stream/call identifiers
- last transcripts
- last tool activity
- tool execution history
- event timeline

### 5. Realtime browser credentialing

`POST /api/realtime/client-secret`

When a ready OpenAI Realtime profile is active, Sonic Calling can mint a short-lived OpenAI Realtime client secret for browser-side or WebRTC-connected clients. When no ready profile exists, the same endpoint returns a structured preview response so local development still works cleanly.

### 6. Twilio live-call entry

`POST /twilio/voice/{session_id}`

Returns TwiML that:

- speaks the opening disclosure line
- starts a bidirectional `<Connect><Stream>`
- passes `session_id`, `agent_name`, and platform metadata as stream parameters

### 7. Live bridge behavior

`/twilio/media-stream/{session_id}` supports two modes:

- **Live mode:** if a ready OpenAI Realtime profile is selected, inbound Twilio audio is forwarded to OpenAI Realtime, model output audio is streamed back to Twilio, and function-call results are written back through `conversation.item.create` plus `response.create`
- **Simulator mode:** if no ready profile is active, Sonic Calling still records normalized Twilio-style events and keeps the operator cockpit useful

## Current OpenAI/Twilio alignment

This repo was aligned against official documentation accessed on **May 1, 2026**:

- OpenAI Realtime:
  - [Realtime conversations guide](https://developers.openai.com/api/docs/guides/realtime-conversations)
  - [Realtime API reference](https://developers.openai.com/api/reference/resources/realtime)
  - [Create client secret](https://developers.openai.com/api/reference/resources/realtime/subresources/client_secrets/methods/create)
- Twilio Voice:
  - [Media Streams overview](https://www.twilio.com/docs/voice/media-streams)
  - [Media Streams WebSocket messages](https://www.twilio.com/docs/voice/media-streams/websocket-messages)
  - [TwiML `<Stream>` reference](https://www.twilio.com/docs/voice/twiml/stream)
- Product-shape inspiration:
  - [VideoSDK platform](https://www.videosdk.live/v1)

## Dashboard preview

![Sonic Calling dashboard preview](./tests/artifacts/sonic-calling-smoke.png)

## Quick start

### 1. Install

```bash
python -m pip install -r apps/api/requirements.txt
npm install
```

### 2. Configure

Copy `.env.example` into your environment or shell and set:

- `OPENAI_API_KEY` for live Realtime bridging and client-secret minting
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, and `TWILIO_FROM_NUMBER` for deploy-time Twilio calling
- `PUBLIC_BASE_URL` and `PUBLIC_WEBSOCKET_BASE` to your public HTTPS/WSS host in deployed environments

You can also add vault-managed profiles from the UI or the provider APIs instead of relying only on environment variables.

### 3. Run locally

```bash
python serve_api.py --port 8000
npm --workspace apps/web run dev -- --host 127.0.0.1 --port 5173
```

### 4. Verify

```bash
python -m pytest tests -q
npm run lint:web
npm run build:web
python -m playwright install chromium
python C:/Users/samee/.codex/skills/webapp-testing/scripts/with_server.py --server "python serve_api.py --port 8000" --port 8000 --server "npm --workspace apps/web run dev -- --host 127.0.0.1 --port 5173" --port 5173 -- python tests/web_smoke.py
```

## Advanced implementation notes

- Twilio bidirectional streams use `audio/x-mulaw` at `8000Hz`; Sonic Calling configures `g711_ulaw` input and output for OpenAI Realtime so the bridge can avoid an extra local transcoding layer
- The BYO vault keeps secrets masked in UI payloads and separates environment-managed defaults from vault-managed profiles
- The operator console can be pointed at a different control plane without rebuilding by appending `?apiBase=http://host:port`
- Live tool execution is shared between the simulator path and OpenAI Realtime function-call events, so the same tool mesh works in both development and production-shaped flows
- The simulator path intentionally remains first-class so teams can work on agent policy, UI, and workflow tooling before live credentials are available
- Event timelines are capped to the most recent entries so the in-memory session store stays lightweight

## Important scope note

This repo now goes well beyond a mock dashboard, but it still does **not** claim to fully certify:

- carrier delivery success
- regional calling-law compliance
- production Twilio routing behavior
- deploy-time WSS termination
- real account quotas or billing behavior on OpenAI/Twilio

Those remain environment-specific go-live tasks.

## License

MIT
