FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/workspace/.venv/bin:$PATH"

RUN pip install --no-cache-dir uv==0.11.24

WORKDIR /workspace
COPY pyproject.toml uv.lock ./
COPY apps/api ./apps/api
COPY deploy/cloud-run/supabase-ca-2021.crt /workspace/certs/supabase-ca-2021.crt
RUN uv sync --frozen --no-dev --project apps/api

WORKDIR /workspace/apps/api
EXPOSE 8000
USER 10001:10001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
