FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
COPY backend/pyproject.toml /workspace/backend/pyproject.toml
COPY backend/app /workspace/backend/app
RUN python -m pip install --no-cache-dir -e '/workspace/backend[test,whisper]'
