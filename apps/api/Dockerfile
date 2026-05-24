FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY pyproject.toml README.md alembic.ini /app/
COPY alembic/ /app/alembic/
COPY src/ /app/src/

RUN pip install --no-cache-dir -e .

EXPOSE 8000
CMD ["uvicorn", "tickerlens_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
