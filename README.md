# Institutional AI Trading Platform

Enterprise-grade foundation for an AI-powered institutional trading platform. The repository contains a Django/DRF backend, PostgreSQL schema, Redis/Celery/Channels infrastructure, Next.js dashboard shell, MT5 broker engine, risk engine, signal engine, analytics, Telegram integration, Docker deployment and operations documentation.

## Run
```bash
cp .env.example .env
docker compose up --build
```

- API: http://localhost:8000/api/v1/
- OpenAPI: http://localhost:8000/api/schema/
- Swagger: http://localhost:8000/api/docs/
- Frontend: http://localhost:3000
