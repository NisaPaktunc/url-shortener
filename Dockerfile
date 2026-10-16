# syntax=docker/dockerfile:1

# ---- Stage 1: build ---------------------------------------------------------
# Installs the Python packages into a virtual environment. Compilers and pip
# caches stay in this stage and never reach the final image.
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Only pyproject.toml is copied here, so this layer is rebuilt only when the
# dependencies change, not on every code change.
WORKDIR /build
COPY pyproject.toml ./
RUN python -c "import tomllib; print('\n'.join(tomllib.load(open('pyproject.toml', 'rb'))['project']['dependencies']))" > requirements.txt \
    && pip install -r requirements.txt

# ---- Stage 2: runtime -------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# The app runs as a normal user, not as root.
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home \
        --shell /usr/sbin/nologin app

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY --chown=app:app alembic.ini ./
COPY --chown=app:app alembic ./alembic
COPY --chown=app:app app ./app
COPY --chown=app:app --chmod=755 docker/entrypoint.sh /entrypoint.sh

USER app
# Only a hint for people: the real port is $PORT, or 8000.
EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
# The port comes from $PORT (Render sets it), or 8000 when it is not set.
# The app writes its own request log lines, so the access log is turned off.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --no-access-log"]
