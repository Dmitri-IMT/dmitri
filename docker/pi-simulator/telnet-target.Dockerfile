FROM python:3.12-alpine

COPY docker/pi-simulator/targets/telnet/server.py /opt/lab/server.py
EXPOSE 23
CMD ["python", "/opt/lab/server.py"]
