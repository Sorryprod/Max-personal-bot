# --- 1. Сборка мини-приложения (пересобирается только при изменении webapp/) ---
FROM node:24-alpine AS webapp
WORKDIR /webapp
COPY webapp/package.json webapp/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --no-audit --no-fund
COPY webapp/ ./
RUN npm run build

# --- 2. Python-зависимости (пересобираются только при изменении requirements.txt) ---
FROM python:3.12-slim AS deps
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /venv
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip /venv/bin/pip install -r requirements.txt

# --- 3. Рантайм ---
FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/venv/bin:$PATH
RUN useradd --create-home --uid 1000 app
WORKDIR /srv
COPY --from=deps /venv /venv
COPY --from=webapp /webapp/dist ./webapp/dist
COPY alembic.ini ./
COPY certs ./certs
COPY migrations ./migrations
COPY app ./app
USER app
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=2)"
# Миграции применяются автоматически при старте
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8080 --proxy-headers --forwarded-allow-ips='*'"]
