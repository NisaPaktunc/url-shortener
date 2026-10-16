# URL Shortener

[![CI](https://github.com/NisaPaktunc/url-shortener/actions/workflows/ci.yml/badge.svg)](https://github.com/NisaPaktunc/url-shortener/actions/workflows/ci.yml)

A simple URL shortener with user accounts and click analytics, built with FastAPI.

> **Status:** Work in progress. You can register, log in, create short links,
> use them to redirect, and see click statistics through the API and in a
> web dashboard.

## Features

- User accounts with login (JWT tokens). Passwords are stored as Argon2 hashes
- Create a short link for any http or https URL (login needed)
- Random 7-character codes (letters and digits)
- Optional custom codes, for example `/mycode`
- Redirect from the short code to the original URL (public, no login)
- Every click is saved with its time, the device type (mobile, desktop,
  tablet or bot) and the referrer
- Clicks are saved in a background task, so redirects stay fast
- A list of your links with their click totals
- Statistics per link: clicks per day, device types and top referrers
  (calculated with SQL `GROUP BY`)
- A web dashboard at `/dashboard`: log in, create links, copy them and see
  charts (clicks per day, devices) and top referrers
- A script that fills the database with demo data for screenshots
- Rate limits for login and link creation, one error format for the whole
  API, and JSON request logs with a request id
- Database migrations with Alembic (they also run automatically when the
  Docker container starts)
- Runs with Docker Compose: the app and a Postgres database, with a volume
  and healthchecks
- Ready for Render.com (`render.yaml`: web service and Postgres)

## Tech stack

- Python 3.12
- FastAPI
- SQLAlchemy and Alembic (SQLite for development and tests, Postgres in Docker)
- argon2-cffi (password hashing) and PyJWT (login tokens)
- user-agents (detects the device type)
- pytest
- Plain HTML, vanilla JavaScript and Chart.js for the dashboard (no build step)

## Project structure

```
alembic/         # database migrations
app/
  main.py        # app entry point
  config.py      # settings
  database.py    # database connection
  security.py    # password hashing and tokens
  errors.py      # one error format and the global error handlers
  rate_limit.py  # rate limiting (slowapi)
  logging_config.py  # JSON logs and the request-logging middleware
  dependencies.py  # get_current_user
  models/        # database tables
  schemas/       # request and response models
  services/      # business logic
  routers/       # API endpoints
  static/        # the dashboard: dashboard.html, css/ and js/ (ES modules)
scripts/         # seed.py fills the database with demo data
.github/workflows/  # CI: ruff and pytest
docker/          # entrypoint.sh: runs migrations, then starts the app
Dockerfile       # multi-stage image, runs as a normal user
docker-compose.yml  # app + Postgres
render.yaml      # Render.com Blueprint
tests/           # automated tests
```

The code is split in layers. A router reads the request and calls a service.
The service does the real work and talks to the database through the models.

## Getting started

You need Python 3.12 or newer.

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. Install the project and the dev tools
pip install -e ".[dev]"

# 3. Create your settings file
cp .env.example .env
```

Open `.env` and set `SECRET_KEY`. It signs the login tokens, so it must be
long, random and private. You can make one like this:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

The app will not start without a `SECRET_KEY` of at least 32 characters.

```bash
# 4. Create the database tables
alembic upgrade head
```

## Run the app

```bash
uvicorn app.main:app --reload
```

Then open:

- http://127.0.0.1:8000/dashboard for the dashboard
- http://127.0.0.1:8000/docs to try the API in your browser
  (use the **Authorize** button to log in)
- http://127.0.0.1:8000/health to check that the app is running

## Run with Docker

This starts the app together with a Postgres database. You need Docker with
the Compose plugin.

```bash
# 1. Create your settings file
cp .env.example .env

# 2. Open .env and fill in two values:
#    SECRET_KEY        python -c "import secrets; print(secrets.token_urlsafe(48))"
#    POSTGRES_PASSWORD letters and digits only, e.g. openssl rand -hex 24

# 3. Build and start
docker compose up --build
```

When the log says `Application startup complete`, check it:

```bash
curl http://127.0.0.1:8000/health      # {"status":"ok"}
```

and open http://127.0.0.1:8000/dashboard. Compose refuses to start with a clear
message if `SECRET_KEY` or `POSTGRES_PASSWORD` is missing.

What happens at start:

1. Postgres starts. Its healthcheck (`pg_isready`) must pass first.
2. The app container runs `alembic upgrade head`, then starts the server.
   If the migration fails, the container stops, so the app never runs on a
   wrong database.
3. The app has a healthcheck too (`GET /health`).

Useful commands:

```bash
docker compose ps                       # shows "healthy" when all is fine
docker compose logs -f app              # follow the app log
docker compose down                     # stop (the data stays in the volume)
docker compose down -v                  # stop and DELETE the database volume
docker compose exec app python -c "print('hi')"   # run something in the container
```

Notes:

- The database lives in the `pgdata` volume, so it survives `docker compose down`.
- `.env` is not copied into the image. Compose passes the values in at start.
- The image runs as a normal user (not root).
- `POSTGRES_PASSWORD` becomes a part of the database URL, so use only letters
  and digits.
- Not included: HTTPS and a reverse proxy (put one in front for real
  use), running several app containers at once (they would all run the
  migration at the same time), and database backups.

## Deploy to Render

[Render](https://render.com) can build the Docker image and run Postgres for
you. The file `render.yaml` (a "Blueprint") describes both, so you do not
click them together by hand.

### What `render.yaml` creates

| Resource | Details |
| -------- | ------- |
| Web service `url-shortener` | Built from the `Dockerfile`. Health check: `GET /health`. Frankfurt region, free plan |
| Postgres `urlshortener-db` | PostgreSQL 16, free plan, same region |

### Environment variables

Render sets them from the file. You only look at them, you do not type them.

| Variable | Value | Where it comes from |
| -------- | ----- | ------------------- |
| `DATABASE_URL` | the database's internal address | Render, from the database |
| `SECRET_KEY` | a random secret | Render generates it once (`generateValue`) |
| `PORT` | the port to listen on | Render sets it; the container uses it |
| `FORWARDED_ALLOW_IPS` | `*` | Trust Render's `X-Forwarded-Proto` header, so short links start with `https://` |
| `TRUSTED_PROXY_HOPS` | `1` | One proxy in front of the app (for rate limits) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Lifetime of a login token |
| `LOG_LEVEL` | `INFO` | Log detail |
| `RATE_LIMIT_ENABLED` | `true` | Rate limits on |
| `LOGIN_RATE_LIMIT` | `5/minute` | Login limit |
| `CREATE_LINK_RATE_LIMIT` | `30/minute` | Link creation limit |

Render gives the database address as `postgresql://...`. The app changes it to
`postgresql+psycopg://...` by itself (`normalize_database_url` in
`app/config.py`).

### Steps

1. Push the project to a GitHub repository (the `.env` file must not be in it).
2. In Render choose **New +, Blueprint**, connect your GitHub account, pick
   the repository and the branch with `render.yaml`.
3. Render shows the two resources. Check them and press **Apply**.
4. Wait for the first build. When the service shows **Live**, open its URL
   and add `/health` (you should see `{"status":"ok"}`) and `/dashboard`.
5. Create an account on the dashboard and make a link.

On every start the container runs `alembic upgrade head` first, so the tables
are created and updated by themselves. The demo data script is not run on
Render.

### Free plan: what to know

(Render's rules change, check [Deploy for Free](https://render.com/docs/free).)

- A free web service **sleeps after 15 minutes** without requests. The next
  request wakes it, which takes about a minute.
- A free Postgres database **expires 30 days after it was created**. Render
  keeps it for 14 more days so you can upgrade, then deletes it with all data.
  For anything you want to keep, change `plan` of the database in
  `render.yaml` to a paid plan (for example `0.1c-256mb`) or upgrade it in the
  Render dashboard.
- Free services have no backups, and the web service has no persistent disk.

### Problems

| What you see | What to do |
| ------------ | ---------- |
| The build or deploy fails | Open the service's **Logs**. The first lines show if the migration failed |
| `SECRET_KEY` error at start | Check **Environment** of the service: `SECRET_KEY` must exist |
| Short links start with `http://` | `FORWARDED_ALLOW_IPS` is missing or not `*` |
| Everybody gets `429` together | Render has two proxies in front: set `TRUSTED_PROXY_HOPS` to `2` |
| A forged `X-Forwarded-For` header gets around the limit | `TRUSTED_PROXY_HOPS` is `0`. Set it to the number of proxies |
| First request is very slow | The free service was asleep |

### Check the rate limit on the live site

Send 6 wrong logins from your computer. The 6th must answer `429`:

```bash
for i in 1 2 3 4 5 6; do
  curl -s -o /dev/null -w "%{http_code} " https://YOUR-APP.onrender.com/auth/login \
    -d "username=nobody@example.com&password=wrong-password-1"
done
```

Then send them again with a different fake `-H "X-Forwarded-For: 1.2.3.$i"` in
each request. If you still get `429` at the 6th, the fake header does not
work, which is what you want.

## Dashboard

Open http://127.0.0.1:8000/dashboard. Create an account (or log in), then:

1. Paste a web address, optionally choose a custom code, and press **Shorten**.
2. Your links are listed with their click totals. **Copy** puts the short
   link in your clipboard.
3. Click a link (or **View stats**) to see its statistics for the last 7, 30
   or 90 days: a line chart of clicks per day, a doughnut chart of device
   types and a table of top referrers.

The dashboard is plain HTML and JavaScript files in `app/static/`. There is
no build step. It uses the API described below, and the login token is kept
in the browser's `localStorage`. When the token expires you are sent back to
the log in form.

Chart.js is loaded from the jsDelivr CDN, so the charts need an internet
connection. The tag is pinned to one version and has an integrity hash, so
the browser refuses a changed file. Without Chart.js the numbers and the
referrer table still work.

### Demo data

To see the dashboard with data (for example for screenshots), run:

```bash
python scripts/seed.py
```

It creates the user `demo@example.com` (password `demo-password-123`) with 5
links and about 500 clicks over 45 days: more clicks on weekdays, one spike
day, mostly phones, and one link without clicks. Options:

| Option | Meaning |
| ------ | ------- |
| `--days N` | How many days of data (7 to 365, default 45) |
| `--seed N` | Random seed. The same seed gives the same data (default 7) |
| `--reset` | Delete the old demo data first. Other users are not touched |
| `--force` | Allow a database that is not SQLite (the script refuses by default) |

Run `alembic upgrade head` first, so the tables exist.

## API

### Register and log in

```bash
# Create an account
curl -X POST http://127.0.0.1:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "me@example.com", "password": "a-long-password"}'

# Log in (this one is a form, and the email goes in "username")
curl -X POST http://127.0.0.1:8000/auth/login \
  -d "username=me@example.com&password=a-long-password"
```

The login answer holds your token:

```json
{"access_token": "eyJhbGciOi...", "token_type": "bearer"}
```

Send the token in the `Authorization` header on every request that needs a
login. A token is valid for 30 minutes by default (`ACCESS_TOKEN_EXPIRE_MINUTES`).

| Endpoint | Status | Meaning |
| -------- | ------ | ------- |
| `POST /auth/register` | 201 | The account was created |
| | 409 | This email is already registered |
| | 422 | The email or password is not valid (password: 8 to 128 characters) |
| `POST /auth/login` | 200 | Login worked, the token is in the answer |
| | 401 | Wrong email or password |

### Create a short link (login needed)

```bash
curl -X POST http://127.0.0.1:8000/links \
  -H "Authorization: Bearer <your token>" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/some/long/page"}'
```

Response (`201 Created`):

```json
{
  "code": "aB3xY9z",
  "short_url": "http://127.0.0.1:8000/aB3xY9z",
  "target_url": "https://example.com/some/long/page",
  "created_at": "2026-10-11T14:30:00"
}
```

To choose your own code, add `custom_code`:

```json
{"url": "https://example.com", "custom_code": "mycode"}
```

A custom code must have 3 to 32 letters or digits. Some words are reserved
because the app uses them (`health`, `docs`, `links`, `auth`, ...).

| Status | Meaning |
| ------ | ------- |
| 201 | The short link was created |
| 401 | No token, or the token is wrong or expired |
| 409 | The custom code is already taken |
| 422 | The URL is not http/https, or the custom code is not valid |
| 503 | No free random code was found (very rare, just try again) |

### List your links (login needed)

```bash
curl http://127.0.0.1:8000/links -H "Authorization: Bearer <your token>"
```

Returns your links, newest first. `total_clicks` counts all clicks since the
link was created. A link without clicks is listed with `0`.

```json
[
  {
    "code": "aB3xY9z",
    "short_url": "http://127.0.0.1:8000/aB3xY9z",
    "target_url": "https://example.com/some/long/page",
    "created_at": "2026-10-11T14:30:00Z",
    "total_clicks": 42
  }
]
```

### Statistics of one link (login needed)

```bash
curl "http://127.0.0.1:8000/links/aB3xY9z/stats?days=30" \
  -H "Authorization: Bearer <your token>"
```

`days` is the number of days to look at, today included. It can be 1 to 365
(default 30).

```json
{
  "code": "aB3xY9z",
  "days": 30,
  "total_clicks": 42,
  "daily": [
    {"date": "2026-09-12", "clicks": 0},
    {"date": "2026-09-13", "clicks": 3}
  ],
  "devices": {"mobile": 25, "desktop": 14, "tablet": 2, "bot": 1},
  "top_referrers": [
    {"referrer": "https://news.example.org/post", "clicks": 17}
  ]
}
```

(`daily` has one entry for every day, shortened here.)

| Status | Meaning |
| ------ | ------- |
| 200 | The statistics |
| 401 | No token, or the token is wrong or expired |
| 404 | The link does not exist, or it belongs to someone else |
| 422 | `days` is not a number from 1 to 365 |

Good to know:

- All numbers in the answer are for the chosen days only. `total_clicks` is
  always the sum of `daily`.
- Days are counted in **UTC**. A click at 01:00 in Istanbul (UTC+3) counts for
  the day before.
- `daily` has an entry for every day, with `0` for days without clicks.
  `devices` always has all four types.
- `top_referrers` has at most 5 entries. Clicks without a referrer are not
  listed. Referrers are grouped by their full address, so two pages of the
  same site are two entries.
- Someone else's link gives the same 404 as a link that does not exist, so
  nobody can find out which codes exist.

### Use a short link (public)

```bash
curl -i http://127.0.0.1:8000/aB3xY9z
```

No login is needed. The app answers `302 Found` with a `Location` header that
holds the original URL. If the code does not exist, the answer is `404 Not Found`.

### What is saved for each click

| Field | Description |
| ----- | ----------- |
| `link_id` | The link that was opened |
| `clicked_at` | Time of the click (UTC) |
| `device_type` | `mobile`, `desktop`, `tablet` or `bot`, found from the `User-Agent` header |
| `referrer` | The `Referer` header, or `null` if the browser did not send one |

A request with no `User-Agent` is saved as `bot`, because real browsers always
send one. Unknown agents that are not clearly a bot, phone or tablet are saved
as `desktop`. Clicks on codes that do not exist are not saved.

The click is saved after the redirect response is sent (FastAPI background
task). If saving fails, the error is logged and the redirect still works.

## Errors, rate limits and logs

### Error format

Every error has the same shape:

```json
{"error": {"code": "not_found", "message": "Short link not found.", "request_id": "3f2c9a..."}}
```

`code` is for programs (`unauthorized`, `not_found`, `conflict`,
`validation_error`, `rate_limited`, `internal_error`, ...), `message` is for
people. A `422` answer also has `details` with one entry per wrong field. The
values you sent are never sent back, so a wrong password field is not echoed.
An unexpected crash gives `500` with a general message. The real error is only
written to the log.

```json
{"error": {"code": "validation_error", "message": "The request data is not valid.",
  "request_id": "2edc...", "details": [{"field": "email", "message": "..."}]}}
```

Every answer has an `X-Request-ID` header, and the same id is in the log line
of that request. If you send your own `X-Request-ID` (letters, digits, `.`,
`_`, `-`, up to 64 characters) it is used instead.

### Rate limits

| Endpoint | Default limit |
| -------- | ------------- |
| `POST /auth/login` | 5 per minute |
| `POST /links` | 30 per minute |

The limit is counted per client IP address. When it is used up the answer is
`429` with a `Retry-After` header (the length of the time window in seconds).
Correct logins count too. Change the limits with `LOGIN_RATE_LIMIT` and
`CREATE_LINK_RATE_LIMIT` (for example `10/minute`), or turn them off with
`RATE_LIMIT_ENABLED=false`.

Two things to know. The counters are kept in the memory of the app process, so
with several processes each one counts alone. And behind a reverse proxy
(like on Render) set `TRUSTED_PROXY_HOPS` to the number of proxies in front of
the app (`1` on Render). The app then takes the client address from the
**right** end of the `X-Forwarded-For` header. The left end is written by the
client, so anyone could fake it and get around the limit. With the default `0`
the header is ignored.

### Logs

The app writes one JSON line per request to the standard output:

```json
{"time": "2026-10-11T16:20:42+00:00", "level": "INFO", "logger": "app.request", "message": "request", "request_id": "cf41...", "method": "POST", "path": "/auth/login", "status": 401, "duration_ms": 240.27}
```

The query string, headers, passwords and tokens are never logged. The
`/health` check is only logged at `DEBUG` level, because it runs every few
seconds. Set the level with `LOG_LEVEL` (`INFO` by default).

## Security notes

- Passwords are hashed with Argon2id. The plain password is never stored or logged.
- Tokens are signed with HS256 using `SECRET_KEY` and expire after a short time.
- A wrong password and an unknown email give the same answer, so nobody can
  find out which emails are registered.
- Emails are saved in lowercase, so `A@x.com` and `a@x.com` are one account.
- Links made before accounts existed have no owner. They still redirect.

- The dashboard builds its page with `textContent` only, never `innerHTML`,
  so text from the server (like a target URL or a referrer) cannot run as code.

**Not included yet:** refresh tokens, a server-side logout (the dashboard
logout only forgets the token in the browser), email verification and
password reset. Rate limiting is per IP address only (no lock per account),
and its counters are not shared between processes. Registration is open to
everybody. The OpenAPI docs at `/docs` still
show FastAPI's default 422 format, not the error format above. Also missing: a Content Security
Policy, a dark theme, deleting or editing links, pagination for the link
list, a time zone setting for statistics, and a filter to leave bots out of
the numbers.

## Database migrations

The tables are created and changed with Alembic.

```bash
alembic upgrade head                                   # apply all migrations
alembic revision --autogenerate -m "what changed"      # make a new migration
alembic downgrade -1                                   # undo the last migration
```

If you have an old `shortener.db` from before migrations existed, delete it
first. The first migration creates all tables from scratch.

## Run the tests

```bash
pytest
```

The tests use a temporary in-memory database, so they never touch your real data.
The dashboard tests check that all files exist, that the JavaScript uses only
element ids that are in the page, and that it never builds HTML from strings.
They do not open a real browser, so look at the dashboard yourself too.

## Check code style

```bash
ruff check .
ruff format --check .
```

The ruff rules are in `pyproject.toml`: errors, import order, modern syntax,
likely bugs, security (`S`), simpler code (`SIM`), comprehensions (`C4`) and
pytest style (`PT`). Tests may use `assert` and fixed passwords.

## Continuous integration

GitHub Actions (`.github/workflows/ci.yml`) runs on every push and pull
request with Python 3.12 and a pip cache: `ruff check`, `ruff format --check`
and `pytest`. It needs no secrets. The workflow only has read access to the code.

The badge at the top of this file uses `NisaPaktunc/url-shortener` as a placeholder. Replace
it with your GitHub user name and repository name.

## Roadmap

- [x] Project setup and health check
- [x] Create short links
- [x] Redirect short links
- [x] Save click details (device type, referrer)
- [x] User accounts and login
- [x] Statistics API
- [x] Analytics dashboard
- [x] Docker and Postgres
- [x] Rate limits, error format, logging, CI
- [x] Render deploy files

## License

MIT
