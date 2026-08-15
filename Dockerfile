FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen --no-dev
COPY pitagora/ ./pitagora/
ENTRYPOINT ["python", "-m", "pitagora"]
