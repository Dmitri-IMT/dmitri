FROM debian:12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends openssh-server \
 && rm -rf /var/lib/apt/lists/* \
 && mkdir -p /run/sshd /var/empty \
 && useradd --create-home --shell /bin/sh labdemo \
 && printf '%s:%s\n' 'labdemo' 'training-only-demo' | chpasswd \
 && printf '%s:%s\n' 'root' 'training-only-demo' | chpasswd

COPY docker/pi-simulator/targets/ssh/sshd_config /etc/ssh/sshd_config

EXPOSE 22
CMD ["sh", "-c", "ssh-keygen -A && exec /usr/sbin/sshd -D -e"]
