# Sonic Calling

A developer-first realtime voice platform for building AI phone agents with **OpenAI Realtime** and **Twilio telephony**.

The product direction is intentionally closer to a **VideoSDK-style developer platform** than a single demo bot:

- polished operator console
- reusable backend primitives
- OpenAI Realtime session templates
- Twilio bidirectional media-stream wiring
- tool-calling agent profiles
- compliance controls
- simulator and smoke-tested local workflow

## What Sonic Calling is

Sonic Calling is a starter platform for:

- outbound and inbound AI phone agents
- appointment reminders and confirmations
- qualification and callback scheduling
- concierge and routing flows
- realtime voice assistants that can call tools, escalate to humans, and keep short conversational turns

## Core stack

- **Frontend:** React + TypeScript + Tailwind-style utility design system
- **Backend:** FastAPI + Python
- **Telephony edge:** Twilio Voice + bidirectional Media Streams
- **Realtime brain:** OpenAI Realtime session templates and Twilio stream bridge
- **Testing:** Pytest + Playwright smoke automation
- **DevEx:** GitHub Actions CI, docs, sample agent profiles, smoke screenshot

## Why this repo is realtime-first instead of cascade-first

This implementation uses a **single live voice brain**:

- OpenAI Realtime is the primary runtime for live speech interaction
- Twilio handles PSTN ingress/egress
- agent tools are modeled as callable business actions
- the local simulator mirrors the call flow without requiring live carrier traffic

This avoids the latency and complexity of a cascade pipeline during live voice turns.

## Architecture

```text
apps/
|-- api/
|   `-- app/
|       |-- services/
|       |   |-- compliance.py
|       |   |-- realtime.py
|       |   |-- realtime_bridge.py
|       |   |-- store.py
|       |   `-- twilio_adapter.py
|       |-- config.py
|       |-- data.py
|       |-- main.py
|       `-- schemas.py
`-- web/
    `-- src/
        |-- App.tsx
        |-- index.css
        `-- main.tsx
tests/
|-- test_api.py
|-- test_realtime.py
|-- web_smoke.py
`-- artifacts/
```

More detail lives in [docs/architecture.md](./docs/architecture.md).

## Dashboard preview

![Sonic Calling dashboard preview](./tests/artifacts/sonic-calling-smoke.png)

## Official docs aligned

This repo was aligned against official documentation accessed on **May 1, 2026**:

- OpenAI Realtime:
  - [Realtime API overview](https://platform.openai.com/docs/guides/realtime/overview)
  - [Realtime conversations](https://platform.openai.com/docs/guides/realtime-model-capabilities)
  - [Realtime with WebSocket](https://platform.openai.com/docs/guides/realtime-websocket)
  - [Realtime with SIP](https://platform.openai.com/docs/guides/realtime-sip)
- Twilio telephony:
  - [Media Streams overview](https://www.twilio.com/docs/voice/media-streams)
  - [WebSocket messages](https://www.twilio.com/docs/voice/media-streams/websocket-messages)
  - [TwiML `<Stream>`](https://www.twilio.com/docs/voice/twiml/stream)
- VideoSDK product shape inspiration:
  - [VideoSDK realtime communication platform](https://www.videosdk.live/v1)

## Product surfaces

- **Operator console:** monitor sessions, compliance state, agent profiles, and contact personas
- **Realtime session template:** generate session configuration for OpenAI Realtime
- **Twilio voice webhook:** returns `<Connect><Stream>` TwiML for live calls
- **Twilio media WebSocket:** starter endpoint for ingesting stream events
- **Local simulator:** run realistic turn-by-turn agent behavior without carrier or model keys

## Quick start

### 1. Backend

```bash
python -m pip install -r apps/api/requirements.txt
uvicorn apps.api.app.main:app --reload
```

### 2. Frontend

```bash
npm install
npm run build:web
npm --workspace apps/web run dev -- --host 127.0.0.1 --port 5173
```

### 3. Environment variables

```bash
PLATFORM_NAME=Sonic Calling
BUSINESS_NAME=Sonic Calling Labs
DISCLOSURE_LINE="Hi, this is the Sonic Calling AI assistant from Sonic Calling Labs on a recorded call."
PUBLIC_BASE_URL=http://127.0.0.1:8000
PUBLIC_WEBSOCKET_BASE=ws://127.0.0.1:8000
OPENAI_API_KEY=
OPENAI_REALTIME_MODEL=gpt-realtime
OPENAI_REALTIME_VOICE=marin
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_FROM_NUMBER=
```

When keys are absent, the simulator and trace engine continue to work in deterministic local mode.

## Verification

```bash
python -m pytest tests -q
npm run build:web
python -m playwright install chromium
python C:/Users/samee/.codex/skills/webapp-testing/scripts/with_server.py --server "python -m uvicorn apps.api.app.main:app --port 8000" --port 8000 --server "npm --workspace apps/web run dev -- --host 127.0.0.1 --port 5173" --port 5173 -- python tests/web_smoke.py
```

The latest audit notes are in [docs/audit.md](./docs/audit.md).

## Important scope note

This repo verifies:

- realtime session blueprints
- Twilio webhook output
- local simulator behavior
- UI workflow
- API contracts

It does **not** claim to live-certify:

- real carrier routing
- per-country calling regulations
- production OpenAI billing or quota behavior
- real Twilio call audio loopback without deploy-time credentials

## License

MIT
