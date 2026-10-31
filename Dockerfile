# syntax=docker/dockerfile:1
# polskiprimal.pl — production image: Tailwind CSS is built in stage 1, the app runs on uvicorn.

# ---- Stage 1: build the Tailwind stylesheet (Node is used only here) -------------------
FROM node:20-alpine AS css
WORKDIR /build
COPY package.json tailwind.config.js ./
RUN npm install --no-audit --no-fund
COPY frontend ./frontend
# Tailwind scans the templates for the classes in use.
COPY app/templates ./app/templates
RUN npm run build:css

# ---- Stage 2: runtime ------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /srv

# Runtime dependencies only: requirements.txt lists test packages after the
# "# Test dependencies" marker, which must not be installed in production.
COPY requirements.txt ./
RUN sed '/^# Test dependencies/,$d' requirements.txt > requirements.runtime.txt \
    && pip install -r requirements.runtime.txt

# Application code and the starter content (used by `python -m app.seed`).
COPY app ./app
COPY content ./content
COPY --from=css /build/app/static/css/tailwind.css ./app/static/css/tailwind.css

# Run as an unprivileged user.
RUN useradd --create-home --uid 10001 appuser && chown -R appuser /srv
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)" || exit 1

# Caddy (a trusted proxy on the private compose network) sets X-Forwarded-* headers.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
