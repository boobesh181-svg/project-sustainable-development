# Backend Dockerfile for Windsurf Sustainable City POC
# Python 3.11 slim image

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# System deps
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY . .

# Default envs (can be overridden)
ENV ENV=docker \
    HOST=0.0.0.0 \
    PORT=8000

# Run Alembic migrations then start app
CMD alembic upgrade head && \
    uvicorn app.main:app --host 0.0.0.0 --port 8000
