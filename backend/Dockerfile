# Backend Dockerfile (canonical backend)
# - Multi-stage to keep runtime lean
# - Entry point outside /app to avoid Windows bind-mount exec-bit issues

FROM python:3.11-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt


FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ENV=docker \
    HOST=0.0.0.0 \
    PORT=8000 \
    UPLOAD_ROOT=/app/uploads

WORKDIR /app

# Runtime deps: libpq for postgres drivers, gosu for privilege drop
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 gosu \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /usr/sbin/nologin --uid 10001 appuser

COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* \
    && rm -rf /wheels

COPY . .

# Install entrypoint outside /app so bind mounts don't overwrite it
COPY scripts/docker_entrypoint.sh /usr/local/bin/docker_entrypoint.sh
RUN chmod +x /usr/local/bin/docker_entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/docker_entrypoint.sh"]
