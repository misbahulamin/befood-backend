from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('admin_wallet', '0004_inventory_and_wallet_types'),
    ]

    operations = [
        migrations.AlterField(
            model_name='adminwallettransaction',
            name='type',
            field=models.CharField(
                choices=[
                    ('customer_payment', 'Customer payment'),
                    ('customer_funding', 'Customer funding'),
                    ('manual_deposit', 'Manual deposit'),
                    ('adjustment', 'Adjustment'),
                    ('refund_reversal', 'Refund reversal'),
                    ('other_income', 'Other income'),
                    ('withdrawal', 'Withdrawal'),
                    ('customer_withdraw', 'Customer withdraw'),
                    ('customer_refund', 'Customer refund'),
                    ('restaurant_settlement', 'Restaurant settlement'),
                    ('rider_payment', 'Rider payment'),
                    ('operational_expense', 'Operational expense'),
                    ('onahar_expense', 'Onahar expense'),
                    ('promotional_cost', 'Promotional cost'),
                    ('platform_expense', 'Platform expense'),
                    ('manual_adjustment', 'Manual adjustment'),
                    ('inventory_purchase', 'Inventory purchase'),
                    ('inventory_purchase_reversal', 'Inventory purchase reversal'),
                    ('referral_commission', 'Referral commission'),
                    ('referral_commission_reversal', 'Referral commission reversal'),
                ],
                max_length=40,
            ),
        ),
    ]
