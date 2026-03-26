FROM python:3.13-slim

WORKDIR /app

COPY agent/pyproject.toml /app/agent/pyproject.toml
COPY web/server/pyproject.toml /app/web/server/pyproject.toml

RUN pip install --no-cache-dir \
    /app/agent \
    /app/web/server

COPY agent/ /app/agent/
COPY web/server/ /app/web/server/

WORKDIR /app/web/server

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
