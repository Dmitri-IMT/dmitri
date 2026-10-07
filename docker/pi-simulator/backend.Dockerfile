FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

RUN apt-get update \
    && apt-get install --no-install-recommends -y fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
