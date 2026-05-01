# Audit

## Scope

Audit target: `sonic-calling`

This audit covers the upgraded repo after adding:

- session ledger APIs
- richer runtime health reporting
- realtime client-secret minting
- OpenAI transport wiring
- Twilio/OpenAI bridge telemetry
- expanded operator cockpit

## Required checks

- Python dependency install
- backend unit and API tests
- frontend lint
- frontend production build
- end-to-end browser smoke over live local servers
- repo-readiness review for docs and CI

## Expected commands

```bash
python -m pip install -r apps/api/requirements.txt
python -m pytest tests -q
npm run lint:web
npm run build:web
python -m playwright install chromium
python C:/Users/samee/.codex/skills/webapp-testing/scripts/with_server.py --server "python -m uvicorn apps.api.app.main:app --port 8000" --port 8000 --server "npm --workspace apps/web run dev -- --host 127.0.0.1 --port 5173" --port 5173 -- python tests/web_smoke.py
```

## Results

- `python -m pip install -r apps/api/requirements.txt`: passed
- `python -m pytest tests -q`: passed with `13/13`
- `npm run lint:web`: passed
- `npm run build:web`: passed
- `python -m playwright install chromium`: passed
- `python C:/Users/samee/.codex/skills/webapp-testing/scripts/with_server.py --server "python -m uvicorn apps.api.app.main:app --port 8000" --port 8000 --server "npm --workspace apps/web run dev -- --host 127.0.0.1 --port 5173" --port 5173 -- python tests/web_smoke.py`: passed

## Smoke artifact

- Playwright screenshot generated at `tests/artifacts/sonic-calling-smoke.png`

## Audit notes

- The repo now has a real OpenAI transport layer and no longer stops at a static session-template demo.
- Browser-side realtime entry is supported through the client-secret endpoint, with structured preview behavior when no live key is configured.
- The Twilio bridge implementation now tracks stream metadata, event counts, transcripts, and tool-call traces inside the session ledger.
- Live carrier routing is still environment-dependent and therefore not fully certified inside this local Windows workspace.
