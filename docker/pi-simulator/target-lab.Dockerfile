FROM debian:12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends samba \
 && rm -rf /var/lib/apt/lists/* \
 && mkdir -p /srv/public

COPY docker/pi-simulator/smb-lab.conf /etc/samba/smb.conf
COPY docker/pi-simulator/targets/smb/README.txt /srv/public/README.txt
RUN chmod 0555 /srv/public && chmod 0444 /srv/public/README.txt

EXPOSE 139 445
CMD ["smbd", "--foreground", "--no-process-group"]
