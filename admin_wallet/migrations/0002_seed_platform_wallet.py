from decimal import Decimal

from django.db import migrations


def seed_platform_wallet(apps, schema_editor):
    AdminWallet = apps.get_model('admin_wallet', 'AdminWallet')
    AdminWallet.objects.get_or_create(
        code='platform',
        defaults={
            'balance': Decimal('0.00'),
            'currency': 'BDT',
            'status': 'active',
            'total_received': Decimal('0.00'),
            'total_manual_added': Decimal('0.00'),
            'total_withdrawn': Decimal('0.00'),
            'total_expenses': Decimal('0.00'),
            'total_customer_payments': Decimal('0.00'),
        },
    )


def unseed_platform_wallet(apps, schema_editor):
    AdminWallet = apps.get_model('admin_wallet', 'AdminWallet')
    AdminWallet.objects.filter(code='platform').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('admin_wallet', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_platform_wallet, unseed_platform_wallet),
    ]
