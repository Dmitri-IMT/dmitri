FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    AGENT_NMAP_PATH=/usr/bin/nmap

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        nmap \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL \
    https://raw.githubusercontent.com/vulnersCom/nmap-vulners/master/vulners.nse \
    -o /usr/share/nmap/scripts/vulners.nse \
    && nmap --script-updatedb

COPY pyproject.toml README.md ./
COPY src ./src

RUN python -m pip install --upgrade pip \
    && python -m pip install .

RUN mkdir -p /app/artifacts

CMD ["python", "-m", "agent.main"]
