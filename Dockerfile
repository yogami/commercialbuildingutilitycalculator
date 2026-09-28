FROM python:3.12-slim

WORKDIR /app

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependency specifications
COPY pyproject.toml uv.lock ./

# Install dependencies into virtual environment
RUN uv sync --frozen --no-dev

# Copy application source
COPY . .

# Set environment path to virtualenv
ENV PATH="/app/.venv/bin:$PATH"
ENV PORT=8000

EXPOSE 8000

CMD ["sh", "-c", "uvicorn commercial_utility_calculator.web.app:app --host 0.0.0.0 --port ${PORT}"]
