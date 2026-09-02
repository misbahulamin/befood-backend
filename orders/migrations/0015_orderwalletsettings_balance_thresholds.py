from decimal import Decimal

from django.db import migrations, models
import django.core.validators


def clamp_threshold_ordering(apps, schema_editor):
    """Ensure existing rows satisfy subscribe > reminder > meal_stop ≥ 0."""
    OrderWalletSettings = apps.get_model('orders', 'OrderWalletSettings')
    for obj in OrderWalletSettings.objects.all():
        min_bal = obj.min_wallet_balance_to_order
        rem = obj.low_balance_reminder_threshold
        stop = obj.meal_stop_threshold
        if min_bal > rem > stop >= 0:
            continue
        if min_bal <= 0:
            obj.min_wallet_balance_to_order = Decimal('500.00')
            obj.low_balance_reminder_threshold = Decimal('300.00')
            obj.meal_stop_threshold = Decimal('200.00')
        else:
            rem = (min_bal * Decimal('0.60')).quantize(Decimal('0.01'))
            stop = (min_bal * Decimal('0.40')).quantize(Decimal('0.01'))
            if not (min_bal > rem > stop >= 0):
                rem = max(min_bal - Decimal('0.02'), Decimal('0.01'))
                stop = max(rem - Decimal('0.01'), Decimal('0.00'))
            if not (min_bal > rem > stop >= 0):
                obj.min_wallet_balance_to_order = Decimal('500.00')
                rem = Decimal('300.00')
                stop = Decimal('200.00')
            obj.low_balance_reminder_threshold = rem
            obj.meal_stop_threshold = stop
        obj.save(
            update_fields=[
                'min_wallet_balance_to_order',
                'low_balance_reminder_threshold',
                'meal_stop_threshold',
            ]
        )


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0014_alter_orderwalletsettings_min_wallet_balance_to_order'),
    ]

    operations = [
        migrations.AddField(
            model_name='orderwalletsettings',
            name='low_balance_reminder_threshold',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('300.00'),
                help_text='Send low-balance reminder when spendable balance is strictly below this amount (BDT).',
                max_digits=12,
                validators=[django.core.validators.MinValueValidator(Decimal('0.00'))],
            ),
        ),
        migrations.AddField(
            model_name='orderwalletsettings',
            name='meal_stop_threshold',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('200.00'),
                help_text='Block automated meal delivery when spendable balance is strictly below this amount (BDT).',
                max_digits=12,
                validators=[django.core.validators.MinValueValidator(Decimal('0.00'))],
            ),
        ),
        migrations.RunPython(clamp_threshold_ordering, migrations.RunPython.noop),
    ]
