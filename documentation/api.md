# API Documentation

DRF routers expose `/api/v1/` endpoints for authentication, users, trading, broker, risk, analytics, subscriptions, Telegram subscribers, notifications and system logs. JWT endpoints are `/api/v1/auth/token/`, `/api/v1/auth/token/refresh/` and `/api/v1/auth/token/verify/`.

OpenAPI schema: `/api/schema/`; Swagger UI: `/api/docs/`.

## Endpoint Groups

- `/api/v1/users/`, `/accounts/`, `/sessions/`
- `/api/v1/brokers/`, `/broker-settings/`, `/trading-accounts/`, `/symbols/`, `/watchlists/`
- `/api/v1/signals/`, `/orders/`, `/open-positions/`, `/closed-trades/`, `/journal/`
- `/api/v1/risk-profiles/`
- `/api/v1/performance/`, `/strategy-statistics/`, `/ai-analysis/`
- `/api/v1/notifications/`, `/telegram-subscribers/`
- `/api/v1/plans/`, `/subscriptions/`, `/invoices/`, `/payments/`, `/refunds/`, `/referrals/`
- `/api/v1/system-logs/`, `/audit-logs/`, `/error-logs/`
