# CLAUDE.md

Guide for working on this project.

## Project

A URL shortener with click analytics. This is a GitHub portfolio project by a
university student, so the code must be readable, tested and well documented.

## Stack

- Python 3.12
- FastAPI (web framework)
- SQLAlchemy 2.x (database layer)
- Alembic (database migrations)
- SQLite for development and tests, Postgres in Docker (only `DATABASE_URL` changes)
- slowapi (rate limiting)
- argon2-cffi (password hashing) and PyJWT (login tokens)
- user-agents (finds the device type from the User-Agent header)
- pytest + httpx (tests)
- ruff (lint and format)
- Plain HTML + Chart.js for the dashboard (no frontend framework)

## Folder structure

```
alembic/         # migrations (versions/ holds one file per change)
app/
  main.py        # creates the FastAPI app and includes routers
  config.py      # settings read from environment variables / .env
  database.py    # engine, session, Base, get_db, get_session_factory
  security.py    # password hashing and JWT helpers (no HTTP code)
  errors.py      # the one error format and the global handlers
  rate_limit.py  # slowapi limiter and the limit functions
  logging_config.py  # JSON log formatter and request-logging middleware
  dependencies.py  # get_current_user
  models/        # SQLAlchemy tables (User, Link, Click)
  schemas/       # Pydantic request and response models
  services/      # business logic (no HTTP code here)
  routers/       # HTTP endpoints, one file per feature
  static/        # dashboard.html, css/dashboard.css, js/*.js (ES modules)
scripts/
  seed.py        # demo data (python scripts/seed.py)
tests/
  conftest.py    # shared fixtures (in-memory database, clients, user)
  sample_*.py    # shared test data (User-Agent strings, emails, passwords)
  helpers.py     # put test data (links, clicks) straight into the database
  test_*.py      # one test file per router or feature
```

## Code rules

- Use type hints on every function.
- Keep functions short. One function should do one thing.
- Keep the layers apart:
  - routers handle HTTP only (read the request, call a service, build the response)
  - services hold the business logic and raise plain Python errors
  - models describe tables, schemas describe request and response data
- Routers turn service errors into HTTP errors (for example 409 or 404).
- Do not hard-code settings. Read them from `app/config.py`.
- Add a short docstring to every module, class and public function.
- Names are in English. Comments are in English.
- Every new endpoint needs at least one test.
- Routers are included in `main.py` in order. `redirect.router` (`/{code}`)
  must stay last, because it matches any single word.
- Words used by the app's own routes must be listed in `RESERVED_CODES`
  (`app/schemas/link.py`), so nobody can use them as a custom code.
- Statistics are calculated by the database (`COUNT`, `GROUP BY`), never by
  counting in Python loops. Python may only fill in empty days with 0.
- Each SQL query of the statistics lives in its own small function in
  `stats_service.py` that only builds the query, so it is easy to read and print.
- Time ranges are in UTC.
- Time columns use `UTCDateTime` (`app/models/utils.py`), never a plain
  `DateTime`. It always gives back timezone-aware UTC values, so the API
  prints every time with "Z" and browsers read it correctly. Never pass a
  datetime without a time zone to the database.

## Errors, rate limits and logs

- Every error answer is `{"error": {"code", "message", "request_id"[, "details"]}}`.
  Routers still raise `HTTPException(detail="...")`; the handlers in
  `app/errors.py` turn it into this format. Do not build error JSON by hand.
- Error answers must never contain the input values (passwords!) or
  internal details. A 500 says nothing about the cause; the log has it.
- A new rate-limited endpoint needs `@limiter.limit(function)` under the
  route decorator, a `request: Request` parameter, a limit setting in
  `config.py`, and a test with the `rate_limits_on` fixture. Tests have
  rate limiting off by default (autouse fixture in `conftest.py`).
- Log with `logging.getLogger(__name__)`. Never log passwords, tokens,
  headers or query strings. Add fields to a log line with `extra=`; the field
  must be listed in `EXTRA_FIELDS` in `logging_config.py`.
- The dashboard reads the error format in `api.js` / `format.js`. If the
  format changes, change both and run the UI check again.

## Deploying (Render)

- `render.yaml` is the Blueprint. It must never contain a secret: `SECRET_KEY`
  uses `generateValue`, `DATABASE_URL` uses `fromDatabase`.
- Every variable in `render.yaml` must be a field of `Settings` (a test checks
  this), except `FORWARDED_ALLOW_IPS`, which uvicorn reads itself.
- Hosts give `postgres://` or `postgresql://` URLs. `normalize_database_url`
  changes them to the psycopg 3 driver. Keep it.
- The container listens on `$PORT` (fallback 8000). Migrations run in
  `docker/entrypoint.sh`, not in a Render `preDeployCommand`.
- Client address for rate limits: never use the left end of `X-Forwarded-For`.
  `client_ip` counts from the right with `TRUSTED_PROXY_HOPS`.
- Render cannot be reached from the sandbox. `tests/test_render.py` only reads
  the file; the first real deploy has to be checked by hand.

## CI

- `.github/workflows/ci.yml` runs `ruff check .`, `ruff format --check .` and
  `pytest` on Python 3.12. Run the same three commands before you push.
- Do not add a secret to the workflow. Tests set their own `SECRET_KEY`.

## Frontend rules (dashboard)

- No build step, no framework, no npm packages. Plain HTML, CSS and ES modules
  in `app/static/`. Chart.js comes from a CDN with a pinned version and a
  `integrity` hash. When you change the version, compute a new hash.
- Never use `innerHTML`, `outerHTML`, `insertAdjacentHTML`, `document.write`
  or `eval`. Build elements with `h()` from `js/dom.js`, which only sets text
  with text nodes. A test checks this.
- One module has one job: `api.js` (requests, saved login), `auth.js`,
  `links.js`, `stats.js`, `format.js` (text for people), `dom.js`, and
  `main.js` (starts everything). Only `api.js` calls `fetch`.
- Element ids used in JavaScript must exist in `dashboard.html`. A test checks
  this. UI text is in English.
- Every screen needs a loading, empty and error state. A 401 sends the user
  back to the log in form (`setUnauthorizedHandler`).
- Answers can arrive in the wrong order. Use a request counter (see
  `stats.js`) so an old answer never replaces a newer one.
- The dashboard is served by `routers/dashboard.py`; the files by a
  `StaticFiles` mount at `/static`. `dashboard` and `static` are reserved codes.

## Docker

- `Dockerfile` has two stages (build, runtime) and runs as the `app` user.
  Dependencies are read from `pyproject.toml`, so there is no second list.
- `docker/entrypoint.sh` runs `alembic upgrade head` and then `exec`s the
  command. Keep migrations first and keep `set -e`.
- `docker-compose.yml` has no secrets. `SECRET_KEY` and `POSTGRES_PASSWORD`
  come from `.env` and are required (`${VAR:?message}`).
- Tests stay on SQLite. `tests/test_deployment.py` only reads the files.
  A change to these files needs a real `docker compose up --build` by hand.

## Demo data

- `python scripts/seed.py` creates `demo@example.com` with links and clicks.
  It refuses a database that is not SQLite unless `--force` is given.
  `seed()` takes `now` and a random seed, so tests get the same data every time.
- Tests that need data should use `tests/helpers.py`, not the seed script.

## Security rules

- Never store, log or return a plain password. Only the Argon2 hash is stored,
  and it is never returned by the API.
- Never hard-code the secret key. It comes from `SECRET_KEY` (at least 32
  characters). The app must refuse to start without it.
- Always pass `algorithms=[...]` when decoding a JWT.
- Login errors must not tell which part was wrong. Unknown email and wrong
  password give the same 401 answer.
- An endpoint that changes or lists user data must use `get_current_user`.
  Only `GET /{code}`, `GET /health` and `/auth/*` are public.
- Do not hide an existing resource behind a 403. If a user asks for something
  that belongs to someone else, answer 404 like it does not exist.

## Database and migrations

- The schema is managed only by Alembic. The app does not create tables.
- After changing a model:
  1. `alembic revision --autogenerate -m "short description"`
  2. Read the new file in `alembic/versions/` and fix it if needed
  3. `alembic upgrade head`
- Never edit a migration that was already shared. Add a new one.
- `tests/test_migrations.py` fails when models and migrations do not match.

## Background tasks

- Work that the response does not need (for example saving a click) runs in
  FastAPI `BackgroundTasks`, so the response stays fast.
- A background task runs after the response is sent. It must open its own
  database session with `get_session_factory`, and must not use the
  request's session.
- A background task must never raise. It catches errors and logs them.

## Testing rules

- Tests use a fresh in-memory SQLite database (see `tests/conftest.py`).
  They must never touch the real `shortener.db` file.
- Fixtures: `client` is logged out, `auth_client` is logged in as the `user`
  fixture. Use `client` to test that something needs a login.
- `tests/__init__.py` sets a test `SECRET_KEY` before the app is imported.
- A fixture switches Argon2 to light settings in tests, so they stay fast.
- The `client` fixture points both the request session (`get_db`) and the
  background-task sessions (`get_session_factory`) to the test database.
- The dashboard has no browser tests. Tests only check files, ids and unsafe
  JavaScript calls. Look at the page in a real browser after UI changes.
- Put test data straight into the database with `tests/helpers.py`
  (`make_link`, `add_clicks`). It is faster than calling the API many times.
- Functions that depend on the current time take a `now` argument. Tests
  pass a fixed time, so exact numbers can be checked and tests never break
  at midnight.
- When testing redirects, pass `follow_redirects=False`.
- `TestClient` waits for background tasks, so a test can check the
  database right after the request.

## Commands

```bash
# Install (with dev tools)
pip install -e ".[dev]"

# Create the tables (needs a .env file with SECRET_KEY)
alembic upgrade head

# Run the tests
pytest

# Check code style (the same checks run in CI)
ruff check .
ruff format --check .

# Start the dev server (dashboard: http://127.0.0.1:8000/dashboard)
uvicorn app.main:app --reload

# Fill the database with demo data
python scripts/seed.py --reset
```

## Working method

The project is built in small steps. Finish only the step that was asked for,
run the tests, and report the result in simple words.
