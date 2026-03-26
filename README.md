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
