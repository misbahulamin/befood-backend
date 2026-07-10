# Generated manually for meal package order refactor

import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Q


def clear_legacy_orders(apps, schema_editor):
    for model_name in ('OrderItem', 'OrderReview', 'OrderStatusHistory', 'Order'):
        Model = apps.get_model('orders', model_name)
        Model.objects.all().delete()

    for app_label, model_name in (
        ('payments', 'PaymentIntent'),
        ('delivery', 'DeliveryAssignment'),
    ):
        try:
            Model = apps.get_model(app_label, model_name)
        except LookupError:
            continue
        Model.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('meals', '0004_seed_monthly_meal_packages'),
        ('orders', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(clear_legacy_orders, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='order',
            name='delivery_address',
        ),
        migrations.RemoveField(
            model_name='order',
            name='delivery_fee',
        ),
        migrations.RemoveField(
            model_name='order',
            name='discount',
        ),
        migrations.RemoveField(
            model_name='order',
            name='notes',
        ),
        migrations.RemoveField(
            model_name='order',
            name='outlet',
        ),
        migrations.RemoveField(
            model_name='order',
            name='payment_method',
        ),
        migrations.RemoveField(
            model_name='order',
            name='status',
        ),
        migrations.RemoveField(
            model_name='order',
            name='subtotal',
        ),
        migrations.RemoveField(
            model_name='order',
            name='tax',
        ),
        migrations.RemoveField(
            model_name='order',
            name='total',
        ),
        migrations.AddField(
            model_name='order',
            name='customer_note',
            field=models.TextField(blank=True, default=''),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='order',
            name='meal',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='orders',
                to='meals.mealcategory',
                default=1,
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='order',
            name='meal_name_snapshot',
            field=models.CharField(default='', max_length=255),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='order',
            name='meal_type_snapshot',
            field=models.CharField(default='daily', max_length=20),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='order',
            name='order_end_date',
            field=models.DateField(default='2026-01-01'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='order',
            name='order_month',
            field=models.CharField(default='2026-01', max_length=7),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='order',
            name='order_start_date',
            field=models.DateField(default='2026-01-01'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='order',
            name='order_status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pending'),
                    ('confirmed', 'Confirmed'),
                    ('active', 'Active'),
                    ('completed', 'Completed'),
                    ('cancelled', 'Cancelled'),
                ],
                default='confirmed',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='order',
            name='per_meal_price_snapshot',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='order',
            name='service_days_count',
            field=models.PositiveIntegerField(default=1),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='order',
            name='total_price_snapshot',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='order',
            name='customer',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='meal_orders',
                to='user_management.customerprofile',
            ),
        ),
        migrations.RenameField(
            model_name='orderstatushistory',
            old_name='timestamp',
            new_name='created_at',
        ),
        migrations.AddConstraint(
            model_name='order',
            constraint=models.UniqueConstraint(
                condition=~Q(order_status='cancelled'),
                fields=('customer', 'order_month'),
                name='unique_non_cancelled_order_per_customer_month',
            ),
        ),
    ]
