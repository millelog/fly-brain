FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev
COPY flybrain ./flybrain
EXPOSE 8420
CMD ["uv", "run", "--frozen", "--no-sync", "uvicorn", "flybrain.server:app", "--host", "0.0.0.0", "--port", "8420"]
