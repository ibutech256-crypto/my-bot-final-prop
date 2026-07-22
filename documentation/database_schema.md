# Database Schema

All core domain tables include UUID, created_at, updated_at, soft-delete fields where business data must be retained, indexes and relationships.

Entities: Users, Accounts, Broker Profiles, Broker Settings, Trading Accounts, Trading Symbols, Watchlists, Signals, Orders, Open Positions, Closed Trades, Risk Profiles, Notifications, Telegram Subscribers, Subscription Plans, Subscriptions, Invoices, Payments, Refunds, Referrals, Performance Analytics, Trade Journals, Strategy Statistics, AI Analysis, System Logs, Audit Logs and Error Logs.

Generate physical PostgreSQL DDL with:
```bash
python manage.py makemigrations
python manage.py sqlmigrate trading 0001
```

## Production Migration Workflow

1. Configure PostgreSQL credentials in `.env`.
2. Run `docker compose run --rm backend python manage.py makemigrations`.
3. Review generated migrations.
4. Run `docker compose run --rm backend python manage.py migrate`.
5. Export schema with `pg_dump --schema-only` for release records.
