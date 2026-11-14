# Read-only API image for Cloud Run (or any container host).
# Build from the repo root, because the prepared site data lives outside backend/:
#   docker build -f backend/Dockerfile -t data-nebula-api .
# Cloud Run runs linux/amd64: on an Apple Silicon Mac add --platform linux/amd64.
#   docker run -p 8080:8080 -e NEBULA_CORS_ORIGINS='["https://<web-domain>"]' data-nebula-api
# Only the API and data/derived/toguz-bulak go in (see /.dockerignore): no pipeline, no tests,
# no .env. The demo-reservoir site is synthetic and stays out.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.8 /uv /usr/local/bin/uv

WORKDIR /srv/backend
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/srv/venv \
    PATH="/srv/venv/bin:$PATH"

# Runtime dependencies only (no dev, no pipeline group), exactly as locked.
COPY backend/pyproject.toml backend/uv.lock backend/.python-version ./
RUN uv sync --frozen --no-default-groups --no-install-project

COPY backend/app ./app
COPY data/derived/toguz-bulak /srv/data/toguz-bulak

ENV NEBULA_DATA_DIR=/srv/data \
    PORT=8080
RUN useradd --system --no-create-home api
USER api

# Cloud Run sets PORT; sh expands it, exec hands signals (shutdown) straight to uvicorn.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port \"$PORT\" --proxy-headers --forwarded-allow-ips='*'"]
