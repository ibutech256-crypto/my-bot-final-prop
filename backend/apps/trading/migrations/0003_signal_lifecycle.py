"""Signal lifecycle / diagnostics columns.

Phases 2, 3 and 7 of the remediation brief require that every signal expose
*why* it is in the state it is in, without an operator having to read the
engine log. That information previously existed only as free text inside
``rationale`` (a Python ``repr`` of a list of confluence names) and as an
overloaded ``status`` string.

This migration is purely additive apart from two widenings:

* ``status`` grows from 16 to 32 characters. The engine has been writing
  ``BLOCKED_RISK_CAP_REACHED`` (24) and ``SHADOW_WOULD_EXECUTE`` (20) through
  ``queryset.update()``, which bypasses both choice validation and, on SQLite,
  length enforcement. On any stricter backend those writes would have raised.
* ``SignalStatus`` gains the members the engine actually emits.

Every new column is nullable or defaulted, so existing rows migrate without a
data backfill and the running dashboard keeps working while the migration
applies.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        # 0002 nulls the dangling Order.signal references left behind by an
        # out-of-band raw DELETE. It must run first: altering Signal.status
        # rebuilds the table on SQLite, and the rebuild runs
        # PRAGMA foreign_key_check, which those orphans fail.
        ("trading", "0002_repair_orphan_order_signals"),
    ]

    operations = [
        migrations.AlterField(
            model_name="signal",
            name="status",
            field=models.CharField(
                choices=[
                    ("DRAFT", "Draft"),
                    ("NO_SETUP", "No setup"),
                    ("WATCHLIST", "Watchlist"),
                    ("WAITING_ENTRY", "Waiting for entry"),
                    ("ACTIVE", "Active"),
                    ("SHADOW_WOULD_EXECUTE", "Shadow - would execute"),
                    ("EXECUTED", "Executed"),
                    ("FILLED", "Filled"),
                    ("REJECTED", "Rejected"),
                    ("BLOCKED", "Blocked"),
                    ("CLOSED_TP", "Closed at take profit"),
                    ("CLOSED_SL", "Closed at stop loss"),
                    ("EXPIRED", "Expired"),
                    ("CANCELLED", "Cancelled"),
                ],
                db_index=True,
                default="ACTIVE",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="signal",
            name="timeframe",
            field=models.CharField(blank=True, db_index=True, default="", max_length=8),
        ),
        migrations.AddField(
            model_name="signal",
            name="tier",
            field=models.CharField(blank=True, db_index=True, default="", max_length=16),
        ),
        migrations.AddField(
            model_name="signal",
            name="lifecycle_stage",
            field=models.CharField(blank=True, db_index=True, default="", max_length=32),
        ),
        migrations.AddField(
            model_name="signal",
            name="block_code",
            field=models.CharField(blank=True, db_index=True, default="", max_length=48),
        ),
        migrations.AddField(
            model_name="signal",
            name="block_reason",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="signal",
            name="htf_status",
            field=models.CharField(blank=True, db_index=True, default="", max_length=24),
        ),
        migrations.AddField(
            model_name="signal",
            name="htf_detail",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.AddField(
            model_name="signal",
            name="confluences",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="signal",
            name="spread_pips",
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=18, null=True),
        ),
        migrations.AddField(
            model_name="signal",
            name="spread_risk_ratio",
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name="signal",
            name="position_size",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name="signal",
            name="risk_pct",
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=8, null=True),
        ),
        migrations.AddField(
            model_name="signal",
            name="lifecycle_json",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddIndex(
            model_name="signal",
            index=models.Index(
                fields=["symbol", "direction", "status"],
                name="trading_sig_sym_dir_status_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="signal",
            index=models.Index(
                fields=["status", "created_at"],
                name="trading_sig_status_created_idx",
            ),
        ),
    ]
