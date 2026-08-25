FROM debian:12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends samba \
 && rm -rf /var/lib/apt/lists/* \
 && mkdir -p /srv/public

COPY docker/pi-simulator/smb.conf /etc/samba/smb.conf

EXPOSE 139 445

CMD ["smbd", "--foreground", "--no-process-group"]
