"""Repair orders whose signal was hard-deleted out of band.

Why this migration exists
-------------------------
``Order.signal`` is declared ``ForeignKey(Signal, on_delete=models.SET_NULL,
null=True)``. The declared intent is therefore explicit: when a signal row goes
away, the order survives with a null reference, because a filled order is an
audit record of real money and must never be destroyed by housekeeping.

At some point 36 of the 87 rows in ``trading_order`` -- every one of them
``FILLED``, all dated 2026-07-20 -- ended up pointing at ``trading_signal``
rows that no longer exist (e.g. ``trading_order.id=3`` references
``signal_id=4470``). Django's ``SET_NULL`` cascade could not have produced
that, so the signals were removed by something that bypassed the ORM: a raw
``DELETE`` from a cleanup script. SQLite does not enforce foreign keys unless
``PRAGMA foreign_keys=ON`` is set for the connection, so the corruption was
accepted silently and lay dormant.

It stopped being dormant with the next schema change. Altering a column on
SQLite is implemented as *rebuild table, copy rows, swap*, and Django runs
``PRAGMA foreign_key_check`` when the schema editor exits. The lifecycle
migration therefore aborted with::

    django.db.utils.IntegrityError: The row in table 'trading_order' with
    primary key '3' has an invalid foreign key: trading_order.signal_id
    contains a value '4470' that does not have a corresponding value in
    trading_signal.id.

Applying the repair as a migration -- rather than as a one-off SQL statement on
the server -- means the fix is versioned, reviewable, and replays identically
on any other environment restored from the same backup.

What it does
------------
Sets ``signal_id = NULL`` on exactly the orders whose referenced signal is
missing: precisely the state Django itself would have produced. No order row is
deleted and no other column is touched, so the trade history and the broker
tickets are preserved in full.
"""

from django.db import migrations


def null_orphan_signal_references(apps, schema_editor):
    """Null ``signal_id`` wherever it points at a non-existent signal."""
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE trading_order
               SET signal_id = NULL
             WHERE signal_id IS NOT NULL
               AND signal_id NOT IN (SELECT id FROM trading_signal)
            """
        )
        repaired = cursor.rowcount
    if repaired:
        print(
            f"\n    Repaired {repaired} order(s) referencing deleted signals "
            f"(signal_id set to NULL, matching on_delete=SET_NULL)."
        )


def noop_reverse(apps, schema_editor):
    """Irreversible by nature: the signal rows they pointed at are gone.

    Declared explicitly so ``migrate trading 0001`` still works instead of
    failing with IrreversibleError; there is simply nothing to restore.
    """


class Migration(migrations.Migration):

    dependencies = [
        ("trading", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(null_orphan_signal_references, noop_reverse),
    ]
