# gstack-test

Prototype workspace for a movie-to-song visual creation flow.

## Structure

- `frontend/` — React + TypeScript + Vite desktop workspace
- `backend/` — FastAPI API + SQLite-backed task model + worker process
- `DESIGN.md` — visual system source of truth
- `office-hours/` — product/design planning docs

## Backend

```bash
cd backend
uv sync --all-groups
source .venv/bin/activate
uvicorn app.main:app --reload
```

In a second terminal:

```bash
cd backend
source .venv/bin/activate
python3 -m app.worker
```

Text workflow configuration:

- `GSTACK_TEXT_API_URL` — your text generation endpoint
- `GSTACK_TEXT_API_KEY` — optional bearer token
- `GSTACK_TEXT_API_MODEL` — optional model name forwarded in the request body
- `GSTACK_TEXT_API_REQUEST_FORMAT` — `prompt` or `chat_completions`
- `GSTACK_TEXT_API_PROMPT_FIELD` — optional request JSON field name for the prompt, defaults to `prompt`
- `GSTACK_TEXT_API_RESPONSE_TEXT_PATH` — optional dot path for the text field in the JSON response
- `GSTACK_TEXT_API_TIMEOUT_SECONDS` — request timeout in seconds, defaults to `180`

If `GSTACK_TEXT_API_URL` is unset, generation tasks will fail fast with a configuration error instead of silently falling back to template data.

Recommended setup:

```bash
cp .env.example .env.local
```

Then edit `.env.local` with your real API values. `scripts/dev-up.sh` will load `.env.local` automatically.

For Zhipu GLM / BigModel, the default `.env.example` is already set to the common `chat/completions` shape:

```bash
GSTACK_TEXT_API_URL=https://open.bigmodel.cn/api/paas/v4/chat/completions
GSTACK_TEXT_API_MODEL=glm-5
GSTACK_TEXT_API_REQUEST_FORMAT=chat_completions
```

Its response usually works without `GSTACK_TEXT_API_RESPONSE_TEXT_PATH`, because the backend already recognizes `choices[0].message.content`.

## Frontend

```bash
cd frontend
npm install
npm run dev
```

Set `VITE_API_BASE_URL` if the API is not running on the default dev API target.
The bundled script uses `http://127.0.0.1:8010`.

## One-command dev startup

```bash
bash scripts/dev-up.sh
```

The script installs Python deps with `uv sync`, installs frontend deps with `npm`, starts API + worker + frontend, and waits for the local health checks to pass.

Optional ports:

```bash
BACKEND_PORT=8010 FRONTEND_PORT=4173 bash scripts/dev-up.sh
```

Example with a real text API:

```bash
cp .env.example .env.local
# edit .env.local
BACKEND_PORT=8010 FRONTEND_PORT=4173 bash scripts/dev-up.sh
```

Direct API smoke test:

```bash
./scripts/test-api.sh
```

Stop everything:

```bash
bash scripts/dev-down.sh
```

## Tests

```bash
cd backend
source .venv/bin/activate
pytest
```
