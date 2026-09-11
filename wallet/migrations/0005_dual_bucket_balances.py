"""Dual-bucket wallet balances + ledger after snapshots.

Depends on production ``0004_live_status_provider_recharge_ref_unique``.
Folds help_text / MinValueValidator alters from unfinished-features.
"""

from decimal import Decimal

import django.core.validators
from django.db import migrations, models
from django.db.models import F


def forwards_split_balances(apps, schema_editor):
    Wallet = apps.get_model('wallet', 'Wallet')
    # Copy legacy total into recharge bucket; commission starts at 0.
    Wallet.objects.all().update(
        recharge_balance=F('balance'),
        commission_balance=Decimal('0.00'),
    )
    bad = list(
        Wallet.objects.exclude(
            balance=F('recharge_balance') + F('commission_balance')
        ).values_list('pk', 'public_id', 'balance', 'recharge_balance', 'commission_balance')
    )
    if bad:
        sample = ', '.join(str(row) for row in bad[:10])
        raise RuntimeError(
            f'Wallet bucket invariant failed for {len(bad)} wallet(s). Sample: {sample}'
        )


def backwards_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('wallet', '0004_live_status_provider_recharge_ref_unique'),
    ]

    operations = [
        migrations.AddField(
            model_name='wallet',
            name='commission_balance',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('0.00'),
                help_text='Referral commission: meal-spendable, not withdrawable.',
                max_digits=12,
                validators=[
                    django.core.validators.MinValueValidator(Decimal('0.00')),
                ],
            ),
        ),
        migrations.AddField(
            model_name='wallet',
            name='recharge_balance',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('0.00'),
                help_text='Withdrawable balance from customer recharges/refunds.',
                max_digits=12,
                validators=[
                    django.core.validators.MinValueValidator(Decimal('0.00')),
                ],
            ),
        ),
        migrations.AddField(
            model_name='wallettransaction',
            name='commission_balance_after',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=12,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='wallettransaction',
            name='recharge_balance_after',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=12,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name='wallet',
            name='balance',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('0.00'),
                help_text='Total spendable = recharge_balance + commission_balance.',
                max_digits=12,
                validators=[
                    django.core.validators.MinValueValidator(Decimal('0.00')),
                ],
            ),
        ),
        migrations.AlterField(
            model_name='wallettransaction',
            name='type',
            field=models.CharField(
                choices=[
                    ('recharge', 'Recharge'),
                    ('withdraw', 'Withdraw'),
                    ('payment', 'Payment'),
                    ('refund', 'Refund'),
                    ('adjustment', 'Adjustment'),
                    ('referral_commission', 'Referral commission'),
                    ('referral_commission_reversal', 'Referral commission reversal'),
                ],
                max_length=40,
            ),
        ),
        migrations.RunPython(forwards_split_balances, backwards_noop),
    ]
