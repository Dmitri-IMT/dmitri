FROM debian:12-slim

COPY --from=ghcr.io/astral-sh/uv:0.9-bookworm-slim /usr/local/bin/uv /usr/local/bin/uv

ARG FFUF_VERSION=2.1.0
ARG FFUF_AMD64_SHA256=fc2c82736c14dcbea4daf3d3cf3878c1c4773008ba45c2bc0fceba7d17b40bb5
ARG NIKTO_VERSION=2.6.0
ARG NIKTO_COMMIT=69681e2e4213c15b85a90c53b2169ecb2a88fb01
ARG NIKTO_DB_SHA256=e221b0ab6db1b3dec26a11674a68216fc6ee690b8b20f07056d4e4ae33ed30a2
ARG ENUM4LINUX_VERSION=1.3.10
ARG ENUM4LINUX_COMMIT=f34e7bb3bc2bcd10267a7257fb3658154434ccf4
ARG TESTSSL_VERSION=3.0.8+dfsg-1
ARG NMAP_VULNERS_COMMIT=47c73ec5addcaad04904f233c6f85dfe76c58ed5
ARG NMAP_VULNERS_SHA256=96ab184c1c2da56a184f2a6e156614c9daf9e7d35142ee6c210bd54a1b312cd4

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
      ca-certificates curl git perl libnet-ssleay-perl libio-socket-ssl-perl \
      libjson-perl libxml-writer-perl dirb "testssl.sh=${TESTSSL_VERSION}" \
      smbclient samba-common-bin python3-ldap3 python3-yaml python3-impacket \
      nmap; \
    rm -rf /var/lib/apt/lists/*; \
    mkdir -p /etc/dmitri /opt/dmitri/tools /usr/local/bin; \
    curl --fail --location --silent --show-error \
      "https://github.com/ffuf/ffuf/releases/download/v${FFUF_VERSION}/ffuf_${FFUF_VERSION}_linux_amd64.tar.gz" \
      --output /tmp/ffuf.tar.gz; \
    echo "${FFUF_AMD64_SHA256}  /tmp/ffuf.tar.gz" | sha256sum --check --status; \
    tar -xzf /tmp/ffuf.tar.gz -C /usr/local/bin ffuf; \
    chmod 0755 /usr/local/bin/ffuf; \
    rm /tmp/ffuf.tar.gz; \
    git clone https://github.com/sullo/nikto.git /opt/dmitri/tools/nikto-${NIKTO_VERSION}; \
    git -C /opt/dmitri/tools/nikto-${NIKTO_VERSION} checkout --detach "${NIKTO_COMMIT}"; \
    test "$(git -C /opt/dmitri/tools/nikto-${NIKTO_VERSION} rev-parse HEAD)" = "${NIKTO_COMMIT}"; \
    echo "${NIKTO_DB_SHA256}  /opt/dmitri/tools/nikto-${NIKTO_VERSION}/program/databases/db_tests" | sha256sum --check --status; \
    printf '#!/bin/sh\nexec perl /opt/dmitri/tools/nikto-%s/program/nikto.pl "$@"\n' "${NIKTO_VERSION}" > /usr/local/bin/nikto; \
    chmod 0755 /usr/local/bin/nikto; \
    git clone https://github.com/cddmp/enum4linux-ng.git /opt/dmitri/tools/enum4linux-ng-${ENUM4LINUX_VERSION}; \
    git -C /opt/dmitri/tools/enum4linux-ng-${ENUM4LINUX_VERSION} checkout --detach "${ENUM4LINUX_COMMIT}"; \
    test "$(git -C /opt/dmitri/tools/enum4linux-ng-${ENUM4LINUX_VERSION} rev-parse HEAD)" = "${ENUM4LINUX_COMMIT}"; \
    test -f /opt/dmitri/tools/enum4linux-ng-${ENUM4LINUX_VERSION}/enum4linux-ng.py; \
    printf '#!/bin/sh\nexec /usr/bin/python3 /opt/dmitri/tools/enum4linux-ng-%s/enum4linux-ng.py "$@"\n' "${ENUM4LINUX_VERSION}" > /usr/local/bin/enum4linux-ng; \
    chmod 0755 /usr/local/bin/enum4linux-ng; \
    test -x /usr/bin/testssl || test -x /usr/bin/testssl.sh; \
    test -r /usr/share/wordlists/dirb/common.txt || test -r /usr/share/dirb/wordlists/common.txt; \
    git clone https://github.com/vulnersCom/nmap-vulners.git /tmp/nmap-vulners; \
    git -C /tmp/nmap-vulners checkout --detach "${NMAP_VULNERS_COMMIT}"; \
    test "$(git -C /tmp/nmap-vulners rev-parse HEAD)" = "${NMAP_VULNERS_COMMIT}"; \
    echo "${NMAP_VULNERS_SHA256}  /tmp/nmap-vulners/vulners.nse" | sha256sum --check --status; \
    install -m 0644 /tmp/nmap-vulners/vulners.nse /usr/share/nmap/scripts/vulners.nse; \
    nmap --script-updatedb; \
    nmap --script-help vulners; \
    rm -rf /tmp/nmap-vulners; \
    rm -rf /opt/dmitri/tools/nikto-${NIKTO_VERSION}/.git /opt/dmitri/tools/enum4linux-ng-${ENUM4LINUX_VERSION}/.git

COPY hardware-agent /src/hardware-agent
COPY hardware-agent/packaging/scan-lock-path /usr/lib/dmitri/scan-lock-path
RUN mkdir -p /usr/lib/dmitri /var/lib/dmitri/updates \
 && tr -d '\r' < /usr/lib/dmitri/scan-lock-path > /usr/lib/dmitri/scan-lock-path.normalized \
 && mv /usr/lib/dmitri/scan-lock-path.normalized /usr/lib/dmitri/scan-lock-path \
 && test "$(cat /usr/lib/dmitri/scan-lock-path)" = /var/lib/dmitri/scan.lock \
 && touch /var/lib/dmitri/scan.lock \
 && chmod 0644 /usr/lib/dmitri/scan-lock-path /var/lib/dmitri/scan.lock
RUN uv venv --python 3.12 /opt/agent \
 && uv pip install --python /opt/agent/bin/python /src/hardware-agent
ENV PATH="/opt/agent/bin:$PATH"

COPY --chmod=0755 docker/pi-simulator/agent-entrypoint.sh /usr/local/bin/agent-entrypoint.sh

ENTRYPOINT ["/usr/local/bin/agent-entrypoint.sh"]
