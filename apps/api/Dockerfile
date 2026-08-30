FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/workspace/.venv/bin:$PATH"

RUN pip install --no-cache-dir uv

WORKDIR /workspace
COPY pyproject.toml uv.lock ./
COPY apps/api ./apps/api
RUN uv sync --frozen --no-dev --project apps/api

WORKDIR /workspace/apps/api
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
