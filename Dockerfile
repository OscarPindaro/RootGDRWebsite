FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 \
    UV_VERSION=0.7.8

RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libatspi2.0-0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir "uv==$UV_VERSION"

RUN groupadd -r appuser && useradd -r -g appuser -d /app appuser
RUN mkdir -p /app/data && chown -R appuser:appuser /app

WORKDIR /app

ENV UV_CACHE_DIR=/tmp/uv-cache \
    UV_PROJECT_ENVIRONMENT=/tmp/venv

COPY --chown=appuser:appuser pyproject.toml uv.lock ./

USER appuser

RUN uv sync --frozen --no-dev --no-install-project

COPY --chown=appuser:appuser . .

RUN uv sync --frozen --no-dev

EXPOSE 8000

CMD ["uv", "run", "--no-sync", "uvicorn", "src.backend.server:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
