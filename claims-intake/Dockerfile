# Build from this directory (where pyproject.toml and uv.lock live):
#   docker buildx build --platform linux/amd64 -t claims-intake .
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY src ./src
COPY data ./data

RUN uv sync --frozen

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000
CMD ["uvicorn", "claims.api.routes:app", "--host", "0.0.0.0", "--port", "8000"]
