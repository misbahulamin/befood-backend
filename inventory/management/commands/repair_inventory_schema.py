"""Rebuild inventory tables when migration state is fake-applied but schema is legacy."""

from __future__ import annotations

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection


REQUIRED_ITEM_COLUMNS = ('name_normalized', 'status', 'default_unit', 'average_unit_cost')
REQUIRED_TABLES = (
    'inventory_inventoryitem',
    'inventory_inventorypurchase',
    'inventory_inventorypurchaseline',
    'inventory_inventorystockmovement',
    'inventory_inventorykitchenusage',
    'inventory_inventorywastage',
    'inventory_inventoryadjustment',
    'inventory_inventoryauditlog',
)


class Command(BaseCommand):
    help = (
        'Detect fake-applied / legacy inventory schema mismatch and rebuild '
        'inventory tables from current migrations (safe when tables are empty).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Drop inventory tables even when they contain rows (destructive).',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report mismatch and planned actions without changing the database.',
        )

    def handle(self, *args, **options):
        force = options['force']
        dry_run = options['dry_run']

        inventory_tables = self._inventory_tables()
        item_columns = self._table_columns('inventory_inventoryitem')
        mismatched = self._is_mismatched(inventory_tables, item_columns)

        self.stdout.write('Inventory tables: ' + (', '.join(inventory_tables) or '(none)'))
        if item_columns:
            self.stdout.write(
                'inventory_inventoryitem columns: ' + ', '.join(item_columns)
            )
        else:
            self.stdout.write('inventory_inventoryitem: missing')

        if not mismatched:
            self.stdout.write(self.style.SUCCESS('Inventory schema already matches models.'))
            return

        self.stdout.write(self.style.WARNING('Inventory schema mismatch detected.'))
        row_counts = {t: self._row_count(t) for t in inventory_tables}
        non_empty = {t: n for t, n in row_counts.items() if n > 0}
        if non_empty:
            detail = ', '.join(f'{t}={n}' for t, n in non_empty.items())
            self.stdout.write(self.style.WARNING(f'Non-empty inventory tables: {detail}'))
            if not force:
                raise CommandError(
                    'Refusing to drop non-empty inventory tables. '
                    'Re-run with --force only if you accept data loss.'
                )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    'Dry run: would drop inventory_* tables, clear inventory '
                    'django_migrations rows, and run migrate inventory.'
                )
            )
            return

        self._drop_inventory_tables(inventory_tables)
        deleted = self._clear_inventory_migration_records()
        self.stdout.write(f'Cleared {deleted} inventory django_migrations row(s).')
        call_command('migrate', 'inventory', verbosity=1)

        after_tables = self._inventory_tables()
        after_cols = self._table_columns('inventory_inventoryitem')
        if self._is_mismatched(after_tables, after_cols):
            raise CommandError(
                'Repair finished but schema still mismatches. '
                f'tables={after_tables} item_columns={after_cols}'
            )

        self.stdout.write(
            self.style.SUCCESS(
                'Inventory schema repaired. '
                f'item columns: {", ".join(after_cols)}'
            )
        )

    def _inventory_tables(self) -> list[str]:
        with connection.cursor() as cursor:
            vendor = connection.vendor
            if vendor == 'sqlite':
                cursor.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' AND name LIKE 'inventory_%' "
                    "ORDER BY name"
                )
                return [row[0] for row in cursor.fetchall()]
            cursor.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = current_schema()
                  AND table_name LIKE 'inventory_%%'
                ORDER BY table_name
                """
            )
            return [row[0] for row in cursor.fetchall()]

    def _table_columns(self, table: str) -> list[str]:
        try:
            with connection.cursor() as cursor:
                description = connection.introspection.get_table_description(
                    cursor, table
                )
        except Exception:
            return []
        if not description:
            return []
        return [col.name for col in description]

    def _row_count(self, table: str) -> int:
        with connection.cursor() as cursor:
            cursor.execute(f'SELECT COUNT(*) FROM {self._qi(table)}')
            return int(cursor.fetchone()[0])

    def _is_mismatched(self, tables: list[str], item_columns: list[str]) -> bool:
        table_set = set(tables)
        if not all(t in table_set for t in REQUIRED_TABLES):
            return True
        cols = set(item_columns)
        return not all(c in cols for c in REQUIRED_ITEM_COLUMNS)

    def _drop_inventory_tables(self, tables: list[str]) -> None:
        if not tables:
            return
        with connection.cursor() as cursor:
            if connection.vendor == 'sqlite':
                cursor.execute('PRAGMA foreign_keys = OFF')
            cascade = ' CASCADE' if connection.vendor != 'sqlite' else ''
            for table in tables:
                self.stdout.write(f'Dropping {table} ...')
                cursor.execute(
                    f'DROP TABLE IF EXISTS {self._qi(table)}{cascade}'
                )
            if connection.vendor == 'sqlite':
                cursor.execute('PRAGMA foreign_keys = ON')

    def _clear_inventory_migration_records(self) -> int:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM django_migrations WHERE app = %s",
                ['inventory'],
            )
            return cursor.rowcount if cursor.rowcount and cursor.rowcount > 0 else 0

    def _qi(self, name: str) -> str:
        return connection.ops.quote_name(name)
