FROM python:3.13-slim

WORKDIR /app

COPY pyproject.toml /app/
RUN pip install --no-cache-dir .

COPY load_neo.py /app/
COPY data/cleaned/ /app/data/

CMD ["python", "load_neo.py"]
