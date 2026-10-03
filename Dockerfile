FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_VERSION=0.7.8

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir "uv==$UV_VERSION"

RUN groupadd --gid 10001 appuser && useradd --uid 10001 --gid appuser --home-dir /app appuser
RUN mkdir -p /app/data/uploads /opt/venv && chown -R appuser:appuser /app /opt/venv

WORKDIR /app

ENV UV_CACHE_DIR=/tmp/uv-cache \
    UV_PROJECT_ENVIRONMENT=/opt/venv

COPY --chown=appuser:appuser pyproject.toml uv.lock ./

USER appuser

RUN uv sync --frozen --no-dev --no-install-project && uv cache clean

COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser alembic/ ./alembic/
COPY --chown=appuser:appuser alembic.ini LICENSE ./

RUN uv sync --frozen --no-dev && uv cache clean

ARG BUILD_COMMIT=unknown
LABEL org.opencontainers.image.revision=$BUILD_COMMIT
ENV ROOTGDR_BUILD_COMMIT=$BUILD_COMMIT

EXPOSE 8000

CMD ["uv", "run", "--no-sync", "uvicorn", "backend.server:app", "--host", "0.0.0.0", "--port", "8000"]
