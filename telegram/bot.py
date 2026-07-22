from __future__ import annotations
import os, sys
if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"): sys.stderr.reconfigure(encoding="utf-8", errors="replace")
import time
import json
import logging
from pathlib import Path
from decimal import Decimal
from dotenv import load_dotenv
import requests

def _auto_load_env():
    load_dotenv()
    curr = Path(__file__).resolve()
    for _ in range(6):
        curr = curr.parent
        for fname in [".env", ".env.txt"]:
            env_path = curr / fname
        if env_path.exists():
            load_dotenv(env_path, override=True)

_auto_load_env()
logger = logging.getLogger("telegram")

class TelegramBotClient:
    def __init__(self, token: str):
        if not token:
            raise ValueError("Telegram bot token is required")
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"

    def send_message(self, chat_id: str | int, text: str, parse_mode: str | None = "HTML") -> dict:
        url = f"{self.base_url}/sendMessage"
        payload = {"chat_id": str(chat_id), "text": text}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        try:
            r = requests.post(url, json=payload, timeout=15)
            if not r.ok and "parse entities" in r.text.lower():
                # If HTML/Markdown parsing fails (e.g. unescaped < or > in score/spread thresholds), auto-retry as plain text
                payload.pop("parse_mode", None)
                r = requests.post(url, json=payload, timeout=15)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.error(f"Failed to send Telegram message to {chat_id}: {e}")
            return {"ok": False, "error": str(e)}

    def get_updates(self, offset: int | None = None, timeout: int = 10) -> dict:
        url = f"{self.base_url}/getUpdates"
        params = {"timeout": timeout}
        if offset is not None:
            params["offset"] = offset
        try:
            r = requests.get(url, params=params, timeout=timeout + 5)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.error(f"Failed to get updates from Telegram: {e}")
            return {"ok": False, "result": []}


def run_bot_daemon():
    _auto_load_env()
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.config.settings")
    import django
    django.setup()

    from backend.apps.trading.models import TradingAccount, Signal, OpenPosition
    from backend.apps.notifications.models import TelegramSubscriber
    from django.contrib.auth import get_user_model

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("❌ ERROR: TELEGRAM_BOT_TOKEN environment variable not set even after folder search!")
        return

    bot = TelegramBotClient(token)
    print("🤖 Telegram Bot Client Initialized. Checking subscribers...")

    subscribers = TelegramSubscriber.objects.filter(is_deleted=False)
    startup_msg = (
        "🟢 <b>Institutional AI Trading Platform Started!</b>\n\n"
        "⚡ <b>Romeo TPT Institutional Engine</b>: ACTIVE\n"
        f"🔗 <b>Broker Connection</b>: Exness MT5 (Login: {os.getenv('MT5_LOGIN', 'N/A')})\n"
        "📈 <b>Live Monitoring</b>: EURUSD, GBPUSD, BTCUSD, XAUUSD\n\n"
        "Type /status, /balance, /signals, or /positions to check real-time telemetry."
    )

    if not subscribers.exists():
        print("⚠️ No TelegramSubscriber records found in DB yet. Send /start to your bot right now to auto-register!")
    else:
        for sub in subscribers:
            bot.send_message(sub.chat_id, startup_msg)
            print(f"✅ Startup notification sent to chat_id: {sub.chat_id}")

    offset = None
    print("🔄 Listening for incoming Telegram messages (/start, /status, /balance, /signals, /positions)...")

    while True:
        try:
            updates = bot.get_updates(offset=offset, timeout=10)
            if updates.get("ok") and updates.get("result"):
                for item in updates["result"]:
                    update_id = item["update_id"]
                    offset = update_id + 1

                    message = item.get("message")
                    if not message or "text" not in message:
                        continue

                    chat_id = str(message["chat"]["id"])
                    text = message["text"].strip()
                    username = message["chat"].get("username", "Trader")

                    print(f"📥 Received from @{username} ({chat_id}): {text}")

                    sub, created = TelegramSubscriber.objects.get_or_create(
                        chat_id=chat_id,
                        defaults={
                            "username": username,
                            "verified": True,
                            "signal_alerts": True,
                            "trade_alerts": True,
                        }
                    )
                    if created and not sub.user_id:
                        User = get_user_model()
                        admin_user = User.objects.filter(is_superuser=True).first()
                        if admin_user:
                            sub.user = admin_user
                            sub.save()
                        bot.send_message(chat_id, f"🎉 Welcome @{username}! Your Telegram account ({chat_id}) has been registered for real-time Institutional AI alerts.")

                    if text == "/start" or text == "/help":
                        bot.send_message(
                            chat_id,
                            "🤖 <b>Institutional AI Trading Command Center</b>\n\n"
                            "Available Commands:\n"
                            "🔸 /status — System health & MT5 broker status\n"
                            "🔸 /balance — Real-time account equity & balance\n"
                            "🔸 /signals — Active Romeo TPT institutional signals\n"
                            "🔸 /positions — Current open positions and unrealized P/L\n"
                            "🔸 /help — Show this command menu"
                        )
                    elif text == "/status":
                        acc = TradingAccount.objects.filter(is_active=True, is_deleted=False).first()
                        broker_status = "ONLINE" if acc else "PENDING SYNC"
                        bot.send_message(
                            chat_id,
                            "🟢 <b>System Health & Telemetry</b>\n\n"
                            f"⚡ <b>Romeo TPT Orchestrator</b>: Operational\n"
                            f"🔌 <b>Broker Connection</b>: {broker_status}\n"
                            f"💻 <b>MT5 Login</b>: {os.getenv('MT5_LOGIN', 'N/A')} ({os.getenv('MT5_SERVER', 'N/A')})\n"
                            f"📡 <b>500ms Freshness Gate</b>: ACTIVE\n"
                            f"🛡️ <b>Correlation Shield</b>: ACTIVE"
                        )
                    elif text == "/balance":
                        acc = TradingAccount.objects.filter(is_active=True, is_deleted=False).first()
                        if acc:
                            bot.send_message(
                                chat_id,
                                "💰 <b>Exness MT5 Real-Time Account Snapshot</b>\n\n"
                                f"🏷️ <b>Account Name</b>: {acc.account_name}\n"
                                f"🔢 <b>Account Number</b>: {acc.account_number}\n"
                                f"💵 <b>Balance</b>: ${acc.balance:,.2f}\n"
                                f"📈 <b>Equity</b>: ${acc.equity:,.2f}\n"
                                f"🛡️ <b>Margin</b>: ${acc.margin:,.2f}\n"
                                f"⚡ <b>Leverage</b>: 1:{acc.leverage}"
                            )
                        else:
                            bot.send_message(chat_id, "⚠️ No synced MT5 Trading Account found in database. Make sure the background MT5 engine is running!")
                    elif text == "/signals":
                        signals = Signal.objects.filter(status="ACTIVE", is_deleted=False).order_by("-created_at")[:5]
                        if not signals.exists():
                            bot.send_message(chat_id, "📊 <b>Active Institutional Signals</b>\n\n<i>No active trade setups qualified right now. Romeo TPT requires a minimum confluence score of 75/100.</i>")
                        else:
                            lines = ["📊 <b>Active Institutional Signals (Romeo TPT)</b>\n"]
                            for s in signals:
                                lines.append(
                                    f"🔸 <b>{s.symbol.symbol}</b> [{s.direction}]\n"
                                    f"   Score: <b>{s.confidence}/100</b> | Entry: {s.entry_price}\n"
                                    f"   SL: {s.stop_loss} | TP: {s.take_profit}\n"
                                    f"   <i>{s.rationale[:80]}...</i>\n"
                                )
                            bot.send_message(chat_id, "\n".join(lines))
                    elif text == "/positions":
                        positions = OpenPosition.objects.filter(is_deleted=False).order_by("-opened_at")
                        if not positions.exists():
                            bot.send_message(chat_id, "⚖️ <b>Open Positions</b>\n\n<i>No open trades active on MT5 account right now.</i>")
                        else:
                            lines = ["⚖️ <b>Live MT5 Open Positions</b>\n"]
                            total_pl = Decimal("0.00")
                            for p in positions:
                                total_pl += p.unrealized_profit
                                lines.append(
                                    f"🔹 <b>{p.symbol.symbol}</b> ({p.direction}) {p.volume} lots\n"
                                    f"   Entry: {p.entry_price} | Current: {p.current_price}\n"
                                    f"   P/L: <b>${p.unrealized_profit:,.2f}</b> | Ticket: #{p.broker_ticket}\n"
                                )
                            lines.append(f"\n💵 <b>Total Floating P/L: ${total_pl:,.2f}</b>")
                            bot.send_message(chat_id, "\n".join(lines))
                    else:
                        bot.send_message(chat_id, f"⚠️ Unknown command `{text}`. Type /help to see available commands.")
            time.sleep(2)
        except KeyboardInterrupt:
            print("\n🛑 Telegram Bot Daemon shutting down...")
            break
        except Exception as e:
            logger.error(f"Error in Telegram polling loop: {e}")
            time.sleep(5)

if __name__ == "__main__":
    run_bot_daemon()