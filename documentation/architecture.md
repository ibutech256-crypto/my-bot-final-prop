# Architecture

Clean enterprise architecture:
Presentation Layer (Next.js) → API Layer (DRF/OpenAPI) → Application Services (Celery/WebSockets) → Domain Layer (Django models and engines) → Trading Engine (MT5 adapter) → Infrastructure (PostgreSQL, Redis, Nginx, Docker) → External Services (Telegram, email, future payment gateways).

The backend is split into accounts, trading, risk, analytics, notifications, subscriptions and system apps. Independent Python packages implement signal generation, risk calculations, broker connectivity, analytics, Telegram and news filtering.
