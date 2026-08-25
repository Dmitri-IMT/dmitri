#!/bin/sh
set -e

install -m600 /shared/agent.env /etc/dmitri/agent.env
set -a; . /etc/dmitri/agent.env; set +a
exec dmitri agent
