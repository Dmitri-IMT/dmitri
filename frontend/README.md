# React app - vulnerability-scanner-device

This is a React project currently under initial development.  
More details, features, and documentation will be added soon.

## Docker

Build and run the frontend container:

```bash
cd frontend
docker compose up --build
```

The app will be available at http://localhost:5173.

To build the image directly:

```bash
cd frontend
docker build -t dmitri-frontend ./frontend-app
```
