# Audit

## Scope

Audit target: `sonic-calling`

## Required checks

- backend unit and API tests
- frontend production build
- end-to-end browser smoke over live local servers
- repo-readiness review for docs and CI

## Expected commands

```bash
python -m pytest tests -q
npm run build:web
python -m playwright install chromium
python C:/Users/samee/.codex/skills/webapp-testing/scripts/with_server.py --server "python -m uvicorn apps.api.app.main:app --port 8000" --port 8000 --server "npm --workspace apps/web run dev -- --host 127.0.0.1 --port 5173" --port 5173 -- python tests/web_smoke.py
```

## Results

- `python -m pip install -r apps/api/requirements.txt`: passed
- `npm install`: passed
- `python -m pytest tests -q`: passed
- `npm run build:web`: passed
- `python -m playwright install chromium`: passed
- `python C:/Users/samee/.codex/skills/webapp-testing/scripts/with_server.py --server "python -m uvicorn apps.api.app.main:app --port 8000" --port 8000 --server "npm --workspace apps/web run dev -- --host 127.0.0.1 --port 5173" --port 5173 -- python tests/web_smoke.py`: passed

## Smoke artifact

- Playwright screenshot generated at `tests/artifacts/sonic-calling-smoke.png`

## Notes

- The live brain is modeled around OpenAI Realtime session configuration and Twilio Media Streams.
- Real carrier audio transport is not locally certified because that requires public deploy targets and live Twilio credentials.
