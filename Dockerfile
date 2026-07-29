FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first (layer caching). The tracing extra is required in
# the production image so Azure Monitor/App Insights export can be enabled via
# environment variables without rebuilding the container.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --extra tracing --no-install-project

# Copy application code
COPY *.py ./
COPY workbench_core/ ./workbench_core/
COPY session-container/appdb.py ./session-container/
COPY session-container/seed_docs/ ./session-container/seed_docs/

ENV PATH="/app/.venv/bin:$PATH"

RUN adduser --disabled-password --gecos "" --uid 1000 appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
