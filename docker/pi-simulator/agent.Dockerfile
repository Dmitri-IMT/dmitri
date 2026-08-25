FROM debian:12-slim

COPY --from=ghcr.io/astral-sh/uv:0.9-bookworm-slim /usr/local/bin/uv /usr/local/bin/uv

RUN apt-get update \
 && apt-get install -y --no-install-recommends nmap ca-certificates \
 && rm -rf /var/lib/apt/lists/* \
 && mkdir -p /etc/dmitri

COPY hardware-agent /src/hardware-agent
RUN uv venv --python 3.12 /opt/agent \
 && uv pip install --python /opt/agent/bin/python /src/hardware-agent
ENV PATH="/opt/agent/bin:$PATH"

COPY --chmod=0755 docker/pi-simulator/agent-entrypoint.sh /usr/local/bin/agent-entrypoint.sh

ENTRYPOINT ["/usr/local/bin/agent-entrypoint.sh"]
