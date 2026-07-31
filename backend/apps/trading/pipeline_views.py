"""HTTP read path for the signal-lifecycle funnel and the strategy configuration.

Why a separate module
---------------------
``run_mt5_engine`` is a *different OS process* from the Django/daphne backend
(they are separate nssm services). The ``FunnelCounters`` instance therefore
lives in the engine's memory and is not reachable from a view. The engine
already publishes its state two ways:

* a ``FUNNEL_UPDATE`` websocket event, for live push, and
* a JSON snapshot file (``PipelineConfig.funnel_snapshot_path``),

and this module exposes the snapshot over HTTP so the dashboard can render the
funnel on first paint, before the first websocket push arrives, and so an
operator can curl it. The views are deliberately read-mostly and never import
``MetaTrader5``: they must keep answering while the engine is restarting.

Endpoints
---------
``GET  /api/v1/funnel/``           - latest funnel snapshot + freshness metadata
``GET  /api/v1/funnel/watchlist/`` - why each current WATCHLIST signal is stuck
``GET  /api/v1/strategy-config/``  - the effective configuration, grouped
``POST /api/v1/strategy-config/``  - re-read .env into the backend process
"""

from __future__ import annotations

import json
import logging
import os
from datetime import timedelta
from pathlib import Path
from typing import Any

from django.conf import settings
from django.db.models import Avg, Count
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.apps.common.permissions import ReadOnlyOrPrivileged
from backend.apps.trading.models import Signal, SignalStatus
from trading_engine import strategy_config
from trading_engine.pipeline_trace import REASON_TEXT, describe

logger = logging.getLogger("trading")

# A snapshot older than this is reported as stale so the dashboard can grey the
# panel out instead of presenting numbers from a dead engine as if they were
# live. The engine writes one every ``funnel_report_every_cycles`` cycles.
STALE_AFTER_SECONDS = 900


def _snapshot_path() -> Path:
    """Resolve the snapshot path the engine writes to.

    ``funnel_snapshot_path`` defaults to the relative ``logs/funnel_snapshot.json``.
    The engine's working directory is the repository root, so relative paths are
    anchored to ``settings.ROOT_DIR`` to make the view independent of however
    daphne happened to be started.
    """
    configured = strategy_config.CONFIG.pipeline.funnel_snapshot_path
    path = Path(configured)
    if not path.is_absolute():
        root = Path(getattr(settings, "ROOT_DIR", Path.cwd()))
        path = root / path
    return path


class FunnelView(APIView):
    """Latest signal-lifecycle funnel snapshot written by the engine."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        path = _snapshot_path()
        if not path.exists():
            # Not an error: the engine writes the first snapshot only after
            # ``funnel_report_every_cycles`` scan cycles.
            return Response(
                {
                    "available": False,
                    "detail": (
                        "No funnel snapshot has been written yet. The engine "
                        "publishes one every "
                        f"{strategy_config.CONFIG.pipeline.funnel_report_every_cycles} "
                        "scan cycles."
                    ),
                    "path": str(path),
                },
                status=status.HTTP_200_OK,
            )

        try:
            raw = path.read_text(encoding="utf-8")
            payload: dict[str, Any] = json.loads(raw)
        except (OSError, json.JSONDecodeError) as exc:
            # A torn read (engine writing while we read) must not 500 the
            # dashboard; the next poll will succeed.
            logger.warning("Funnel snapshot unreadable at %s: %s", path, exc)
            return Response(
                {"available": False, "detail": f"Snapshot unreadable: {exc}", "path": str(path)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        age = max(0.0, timezone.now().timestamp() - os.path.getmtime(path))
        payload.update({
            "available": True,
            "path": str(path),
            "age_seconds": round(age, 1),
            "stale": age > STALE_AFTER_SECONDS,
            "shadow_mode": strategy_config.CONFIG.pipeline.shadow_mode,
        })
        return Response(payload)


class FunnelWatchlistView(APIView):
    """Why every currently-open WATCHLIST signal has not been executed.

    This is Phase 3 of the brief expressed as an endpoint: previously an
    operator could see 501 WATCHLIST rows and no reason for any of them. Each
    row now carries ``block_code``/``block_reason``, and this view aggregates
    them so the dominant blocker is visible at a glance.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            hours = max(1, min(168, int(request.query_params.get("hours", 24))))
        except (TypeError, ValueError):
            hours = 24
        since = timezone.now() - timedelta(hours=hours)

        rows = (
            Signal.objects.filter(
                is_deleted=False,
                status=SignalStatus.WATCHLIST,
                created_at__gte=since,
            )
            .select_related("symbol")
            .order_by("-confidence", "-created_at")
        )

        by_reason = (
            rows.values("block_code")
            .annotate(count=Count("id"), avg_score=Avg("confidence"))
            .order_by("-count")
        )
        reasons = [
            {
                "code": entry["block_code"] or "UNSPECIFIED",
                "text": describe(entry["block_code"]) if entry["block_code"] else
                        "no machine-readable reason recorded (signal predates migration 0002)",
                "count": entry["count"],
                "avg_score": float(entry["avg_score"] or 0),
            }
            for entry in by_reason
        ]

        signals = [
            {
                "id": s.id,
                "symbol": s.symbol.symbol if s.symbol else None,
                "timeframe": s.timeframe,
                "direction": s.direction,
                "score": float(s.confidence or 0),
                "tier": s.tier,
                "lifecycle_stage": s.lifecycle_stage,
                "block_code": s.block_code,
                "block_reason": s.block_reason,
                "htf_status": s.htf_status,
                "spread_pips": float(s.spread_pips) if s.spread_pips is not None else None,
                "created_at": s.created_at,
            }
            for s in rows[:200]
        ]

        return Response({
            "window_hours": hours,
            "total": rows.count(),
            "reasons": reasons,
            "signals": signals,
        })


class StrategyConfigView(APIView):
    """Effective strategy configuration, and a way to re-read it from ``.env``.

    ``POST`` reloads this (the backend) process only. The engine runs in its own
    process and re-reads the environment at startup, so a threshold change still
    requires ``nssm restart TradingMT5Engine`` to affect trading. The response
    says so explicitly rather than implying the change is live.
    """

    permission_classes = [ReadOnlyOrPrivileged]

    @staticmethod
    def _grouped() -> dict[str, dict[str, Any]]:
        grouped: dict[str, dict[str, Any]] = {}
        for dotted, value in strategy_config.CONFIG.as_dict().items():
            group, _, name = dotted.partition(".")
            grouped.setdefault(group, {})[name] = value
        return grouped

    def get(self, request):
        return Response({
            "config": self._grouped(),
            "flat": strategy_config.CONFIG.as_dict(),
            "shadow_mode": strategy_config.CONFIG.pipeline.shadow_mode,
            "reason_codes": REASON_TEXT,
        })

    def post(self, request):
        try:
            strategy_config.reload()
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Strategy configuration reload failed")
            return Response(
                {"detail": f"Reload failed, previous configuration retained: {exc}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        logger.info("Strategy configuration reloaded via API by %s", request.user)
        return Response({
            "detail": (
                "Configuration re-read from the environment for the backend "
                "process. The trading engine runs in a separate process: restart "
                "TradingMT5Engine for threshold changes to affect live decisions."
            ),
            "config": self._grouped(),
        })
