FROM python:3.11-slim AS base

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --upgrade pip

COPY src ./src

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
    