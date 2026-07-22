from __future__ import annotations
import logging
from celery import shared_task
from django.db.models import Count, Sum
from backend.apps.analytics_app.models import PerformanceAnalytics
from backend.apps.trading.models import BrokerProfile, ClosedTrade, TradingAccount
logger = logging.getLogger("trading")

@shared_task(bind=True, autoretry_for=(ConnectionError, TimeoutError), retry_backoff=True, retry_kwargs={"max_retries": 5})
def broker_heartbeat(self) -> dict:
    active = BrokerProfile.objects.filter(is_active=True, is_deleted=False).values("broker_type").annotate(count=Count("id"))
    payload = {row["broker_type"]: row["count"] for row in active}
    logger.info("broker heartbeat", extra={"active_brokers": payload})
    return {"status": "ok", "active_brokers": payload}

@shared_task
def recompute_performance() -> dict:
    updated = 0
    for account in TradingAccount.objects.filter(is_deleted=False):
        trades = ClosedTrade.objects.filter(account=account, is_deleted=False).order_by("closed_at")
        totals = trades.aggregate(net=Sum("profit"), count=Count("id"))
        logger.info("performance account summary", extra={"account": account.account_number, "summary": totals})
        updated += 1
    return {"status": "completed", "accounts_processed": updated}
