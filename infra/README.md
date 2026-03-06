# Infrastructure

This directory hosts shared infrastructure assets for local development.

## docker-compose.yml
- Spins up the FastAPI backend (built from `backend/`) and a PostgreSQL 16 instance.
- Provides a named volume (`db_data`) for persistent database storage.

## env.example
- Template for environment variables consumed by docker-compose and various services.
- Copy to `.env` (not committed) and adjust secrets before running the stack.

## Next Steps
- Add Traefik/NGINX reverse proxy definitions if TLS termination is needed locally.
- Define production-ready infrastructure-as-code (Terraform/Ansible) when targeting deployment environments.
