# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app

# Kopiowanie plików konfiguracyjnych uv
COPY pyproject.toml uv.lock ./

# Instalacja zależności produkcyjnych
RUN uv sync --frozen --no-dev --no-install-project

# Kopiowanie kodu źródłowego aplikacji
COPY src/ ./src/
COPY dags/ ./dags/

# Instalacja projektu
RUN uv sync --frozen --no-dev

# Obraz docelowy (runtime)
FROM python:3.12-slim-bookworm AS runner

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PORT=8080 \
    PATH="/app/.venv/bin:$PATH"

# Kopiowanie środowiska wirtualnego i kodu ze stadium builder
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src

EXPOSE 8080

# Uruchomienie FastAPI za pomocą Uvicorn
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
