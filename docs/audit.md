# Audit

## Scope

Audit target: `sonic-calling`

This audit covers the upgraded repo after adding:

- a bring-your-own API vault
- a runtime tool mesh
- live OpenAI Realtime function-call output handling
- deterministic API launching with `serve_api.py`
- a richer operator cockpit

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
python C:/Users/samee/.codex/skills/webapp-testing/scripts/with_server.py --server "python serve_api.py --port 8010" --port 8010 --server "npm --workspace apps/web run dev -- --host 127.0.0.1 --port 5174" --port 5174 -- powershell -Command "$env:SONIC_WEB_URL='http://127.0.0.1:5174/?apiBase=http://127.0.0.1:8010'; python tests\web_smoke.py"
```

## Results

- `python -m pip install -r apps/api/requirements.txt`: previously passed
- `python -m pytest tests -q`: passed with `15/15`
- `npm run lint:web`: passed
- `npm run build:web`: passed
- `npm run audit`: passed
- `python -m playwright install chromium`: previously passed
- `python C:/Users/samee/.codex/skills/webapp-testing/scripts/with_server.py --server "python serve_api.py --port 8010" --port 8010 --server "npm --workspace apps/web run dev -- --host 127.0.0.1 --port 5174" --port 5174 -- powershell -Command "$env:SONIC_WEB_URL='http://127.0.0.1:5174/?apiBase=http://127.0.0.1:8010'; python tests\web_smoke.py"`: passed

## Smoke artifact

- Playwright screenshot generated at `tests/artifacts/sonic-calling-smoke.png`

## Audit notes

- The repo now has a true BYO provider layer instead of environment variables only.
- Tool execution is covered at both the simulator layer and the OpenAI Realtime bridge layer.
- `serve_api.py` avoids ambiguous `apps.api.app.main` resolution on machines that already have another `apps` package on the Python path.
- The browser console can target alternate API hosts using the `?apiBase=` override, which makes smoke and staging checks more reliable.
- Live carrier routing is still environment-dependent and therefore not fully certified inside this local Windows workspace.
