FROM debian:12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends vsftpd \
 && rm -rf /var/lib/apt/lists/* \
 && mkdir -p /srv/ftp /var/run/vsftpd/empty \
 && chmod 0555 /srv/ftp /var/run/vsftpd/empty

COPY docker/pi-simulator/targets/ftp/vsftpd.conf /etc/vsftpd.conf
COPY docker/pi-simulator/targets/ftp/README.txt /srv/ftp/README.txt

EXPOSE 21
CMD ["/usr/sbin/vsftpd", "/etc/vsftpd.conf"]
