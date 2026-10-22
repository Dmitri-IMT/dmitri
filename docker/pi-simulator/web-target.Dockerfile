FROM nginx:1.27-alpine

RUN apk add --no-cache openssl \
 && mkdir -p /usr/share/nginx/html/assets /etc/nginx/certs \
 && openssl req -x509 -nodes -days 3650 -newkey rsa:1024 \
      -sha1 \
      -keyout /etc/nginx/certs/lab.key \
      -out /etc/nginx/certs/lab.crt \
      -subj '/CN=dmitri-targeted-lab.invalid' \
 && chmod 0600 /etc/nginx/certs/lab.key

COPY docker/pi-simulator/targets/web/nginx.conf /etc/nginx/conf.d/default.conf
COPY docker/pi-simulator/targets/web/index.html /usr/share/nginx/html/index.html
COPY docker/pi-simulator/targets/web/env.fixture /usr/share/nginx/html/.env
COPY docker/pi-simulator/targets/web/git-head.fixture /usr/share/nginx/html/.git/HEAD
COPY docker/pi-simulator/targets/web/git-config.fixture /usr/share/nginx/html/.git/config
COPY docker/pi-simulator/targets/web/config.fixture /usr/share/nginx/html/config.json
COPY docker/pi-simulator/targets/web/backup.fixture /usr/share/nginx/html/backup.zip
COPY docker/pi-simulator/targets/web/database.fixture /usr/share/nginx/html/database.sql
COPY docker/pi-simulator/targets/web/error.fixture /usr/share/nginx/html/error.log
COPY docker/pi-simulator/targets/web/actuator.fixture /usr/share/nginx/html/actuator/env
COPY docker/pi-simulator/targets/web/metrics.fixture /usr/share/nginx/html/prometheus
COPY docker/pi-simulator/targets/web/assets-note.txt /usr/share/nginx/html/assets/notes.txt
COPY docker/pi-simulator/targets/web/admin.html /usr/share/nginx/html/admin/index.html

EXPOSE 80 443
