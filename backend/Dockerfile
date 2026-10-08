# Built from the repository root, so the image can carry data/ and samples/:
#   docker build -f backend/Dockerfile .

# Build stage: uv installs the locked dependencies into /app/.venv.
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# Dependencies first, so this layer is reused until the lockfile changes.
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY backend/src ./src
RUN uv sync --locked --no-dev

# Runtime stage: no uv, no build tools, non-root user.
FROM python:3.13-slim-bookworm AS runner

# Tesseract reads scanned leases (PDFs without a text layer).
RUN apt-get update \
    && apt-get install --yes --no-install-recommends tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --system --uid 1001 --no-create-home app

WORKDIR /app
COPY --from=builder --chown=app:app /app /app
COPY --chown=app:app data ./data
COPY --chown=app:app samples ./samples
# Reported photos live here; Compose mounts a volume over it.
RUN mkdir uploads && chown app:app uploads

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/app/data \
    SAMPLES_DIR=/app/samples \
    UPLOADS_DIR=/app/uploads

USER app
EXPOSE 8000

CMD ["uvicorn", "truelinks.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
