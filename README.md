# polskiprimal.pl

Polish healthy-food / farm-to-table platform. **Phase 1 (Option A):** FastAPI +
Amazon S3 (JSON objects), no database. Server-rendered Jinja2 + HTMX + Alpine.js +
Tailwind CSS. UI is in Polish.

The priority is a **fast public launch**: the site runs and is deployable before auth,
calendar, and reservations are finished.

## Project structure

```
app/
  main.py          # create_app() factory + module-level `app`
  config.py        # pydantic-settings (reads env / .env)
  templating.py    # shared Jinja2 instance + theme tokens
  routers/         # HTTP endpoints (public: / and /health)
  services/        # business logic (added in later tasks)
  models/          # Pydantic data shapes (added in later tasks)
  storage/         # StorageBackend interface + S3 impl (added in later tasks)
  templates/       # Jinja2 templates (base layout + homepage)
  static/          # static assets
tests/             # pytest suite
pyproject.toml
requirements.txt
.env.example
```

## Quick start with Docker (one command)

```bash
docker compose up --build
```

Open http://localhost. No `.env`, database or AWS account is needed (starter content from
`content/` is loaded into the in-memory backend). Production with automatic HTTPS, DNS
setup and environment variables: see [DEPLOY.md](DEPLOY.md).

## Quick start (local dev, without Docker)

Requires Python 3.11+.

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. (Optional) configure environment
copy .env.example .env    # Windows
# cp .env.example .env    # macOS/Linux

# 4. Run the app (starts even with no .env present)
uvicorn app.main:app --reload
```

Then open http://localhost:8000 — and http://localhost:8000/health for the health check.
API docs are at http://localhost:8000/docs.

## Content

Starter content lives in `content/` and mirrors the storage key layout
(`categories/`, `blog/`, `config/theme.json`). Edit the JSON/Markdown via GitHub, then:

```bash
STORAGE_BACKEND=memory uvicorn app.main:app --reload   # seeds itself on startup, no AWS needed
python -m app.seed                                     # upload to the configured backend (S3); skips existing objects
python -m app.seed --overwrite                         # replace existing objects with the repo versions
```

Colors and font are set in `config/theme.json` (`primary_color`, `accent_color`,
`font_family`) and applied on the next page load.

## Running tests

```bash
pip install -r requirements.txt
pytest
```

The tests verify the `/health` endpoint returns 200 and that the app imports and starts
with **no** optional environment variables (payment / DB / AWS) set.
