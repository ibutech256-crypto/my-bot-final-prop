"""Position synchronisation daemon.

v2.4 — Module 1 (IPC stability) + Module 9 (race conditions / dead code)
------------------------------------------------------------------------
This runs as a ``threading.Thread(daemon=True)`` started by
``run_mt5_engine.Command.handle``, i.e. **inside the same OS process** as the
main strategy loop and the ScaleOutEngine.

Two defects made that arrangement actively harmful:

1. ``mt5.shutdown()`` on every cycle — the IPC race
   ``run_once()`` ended with ``mt5.shutdown()`` and began with
   ``connect_mt5()``, which called ``mt5.initialize()`` + ``mt5.login()``.
   The ``MetaTrader5`` extension module keeps **one process-wide IPC channel**,
   so this thread tore down and re-established the very connection the main
   loop and ScaleOutEngine were using — once per second, forever. Any call
   made by another thread inside that window failed with
   ``(-10004, 'No IPC connection')``. That is the true origin of the
   intermittent -10004 errors; it is a same-process thread race, not Windows
   Session 0 isolation and not duplicate service instances. This daemon no
   longer initialises or shuts down the terminal link: it verifies the shared
   session and otherwise leaves it strictly alone.

2. Competing trade management
   ``ScaleOutEngine`` already performs the 50% partial close and the
   stop-to-breakeven shift, and every order is submitted to the broker with a
   real ``take_profit``, so MT5 closes the position at target server-side.
   This daemon independently attempted its own partial close at 1R and its own
   full close at 2R against the same tickets, so both components could act on
   one position in the same second and double-close it. Broker-side actions
   are removed here; ScaleOutEngine is the single owner of trade management.

Removed dead code
-----------------
``check_tp1`` and ``check_tp2`` were never reachable — ``run_once`` called
``execute_partial_close`` / ``close_full_position`` directly. ``check_tp1``
also referenced an undefined ``entry_price`` (its parameter is named ``entry``),
so it would have raised ``NameError`` the moment it was wired up, and it moved
the stop to breakeven *without ever testing whether TP1 had been reached* —
which on a 0.01-lot account (the common case here) meant every position would
have been strangled at entry. Both methods are deleted rather than repaired,
because their responsibility now belongs to ScaleOutEngine.

This daemon's remaining job is exactly one thing: keep the Django ``OpenPosition``
rows faithful to MT5, which is what the dashboard and API read from.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from decimal import Decimal

import MetaTrader5 as mt5

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.config.settings")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import django  # noqa: E402

django.setup()

from backend.apps.trading.models import OpenPosition  # noqa: E402

logger = logging.getLogger("trading")

# Seconds between synchronisation passes.
SYNC_INTERVAL_SECONDS = float(os.getenv("POSITION_SYNC_INTERVAL", "1.0"))
# Backoff applied after an unexpected error so a persistent fault cannot spin.
ERROR_BACKOFF_SECONDS = float(os.getenv("POSITION_SYNC_ERROR_BACKOFF", "5.0"))


class PositionManager:
    """Keeps ``OpenPosition`` rows in sync with the live MT5 terminal."""

    def __init__(self) -> None:
        self.running = False
        self.last_check: dict[str, float] = {}
        self.sync_count = 0

    # ------------------------------------------------------------------ #
    # Connection
    # ------------------------------------------------------------------ #

    @staticmethod
    def mt5_session_ready() -> bool:
        """Report whether the shared, process-wide MT5 session is usable.

        Deliberately read-only. The owner of the connection lifecycle is
        ``MT5Client`` in the main thread; initialising or shutting down from
        here is what caused the -10004 race described in the module docstring.
        """
        try:
            return mt5.terminal_info() is not None and mt5.account_info() is not None
        except Exception:
            return False

    # ------------------------------------------------------------------ #
    # Synchronisation
    # ------------------------------------------------------------------ #

    def mark_closed(self, db_pos: OpenPosition, status: str) -> None:
        """Flag a DB position as closed and propagate status to its signal.

        Previously invoked as ``self.check_sl_hit(None)``, whose body
        immediately dereferenced ``pos.ticket`` and raised
        ``AttributeError: 'NoneType' object has no attribute 'ticket'``. That
        fired every time a position disappeared from MT5 — i.e. on every single
        close — and aborted the rest of the synchronisation pass, leaving stale
        rows on the dashboard.
        """
        if db_pos is None:
            return
        try:
            if db_pos.order and db_pos.order.signal:
                db_pos.order.signal.status = status
                db_pos.order.signal.save(update_fields=["status"])
        except Exception as exc:
            logger.warning("Could not update signal status for %s: %s",
                           db_pos.broker_ticket, exc)
        db_pos.is_deleted = True
        db_pos.save(update_fields=["is_deleted"])

    def run_once(self) -> None:
        """One synchronisation pass. Never mutates the broker."""
        if not self.mt5_session_ready():
            # The main thread owns reconnection; just skip this pass.
            return

        positions = mt5.positions_get()
        if positions is None:
            logger.debug("positions_get() returned None: %s", mt5.last_error())
            return

        live_by_ticket = {str(p.ticket): p for p in positions}
        db_positions = list(OpenPosition.objects.filter(is_deleted=False))

        # --- Retire DB rows whose broker position no longer exists ---------
        for dbp in db_positions:
            if dbp.broker_ticket in live_by_ticket:
                continue
            # Distinguish a stop-out from a target hit where we can: if the
            # last known price sat on the losing side of entry, call it SL.
            status = "CLOSED_SL"
            try:
                if dbp.entry_price is not None and dbp.current_price is not None:
                    gained = (dbp.current_price - dbp.entry_price
                              if str(dbp.direction).upper().endswith("BUY")
                              else dbp.entry_price - dbp.current_price)
                    status = "CLOSED_TP" if gained > 0 else "CLOSED_SL"
            except Exception:
                pass
            self.mark_closed(dbp, status)

        # --- Refresh live rows ---------------------------------------------
        for dbp in db_positions:
            pos = live_by_ticket.get(dbp.broker_ticket)
            if pos is None:
                continue
            try:
                dbp.current_price = Decimal(str(pos.price_current))
                dbp.unrealized_profit = Decimal(str(pos.profit))
                dbp.volume = Decimal(str(pos.volume))
                # Reflect broker-side SL moves (ScaleOutEngine breakeven shifts)
                # so the dashboard does not display a stale stop.
                if pos.sl:
                    dbp.stop_loss = Decimal(str(pos.sl))
                if pos.tp:
                    dbp.take_profit = Decimal(str(pos.tp))
                dbp.save(update_fields=[
                    "current_price", "unrealized_profit", "volume",
                    "stop_loss", "take_profit",
                ])
            except Exception as exc:
                logger.warning("Position sync failed for ticket %s: %s",
                               dbp.broker_ticket, exc)

        self.sync_count += 1

    def run_loop(self) -> None:
        self.running = True
        while self.running:
            try:
                self.run_once()
                time.sleep(SYNC_INTERVAL_SECONDS)
            except KeyboardInterrupt:
                self.running = False
            except Exception as exc:
                logger.exception("PositionManager sync error: %s", exc)
                time.sleep(ERROR_BACKOFF_SECONDS)


if __name__ == "__main__":
    PositionManager().run_loop()
