from django.db import migrations, models


def backfill_meal_period_snapshot(apps, schema_editor):
    Order = apps.get_model('orders', 'Order')
    for order in Order.objects.select_related('meal').all().iterator():
        period = None
        meal = getattr(order, 'meal', None)
        if meal is not None:
            period = getattr(meal, 'meal_period', None) or None
        if not period:
            if order.meal_type_snapshot == 'daily':
                period = 'lunch'
            else:
                period = 'both'
        order.meal_period_snapshot = period
        order.save(update_fields=['meal_period_snapshot'])


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0003_order_delivery'),
        ('meals', '0009_package_meal_period'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='meal_period_snapshot',
            field=models.CharField(
                help_text='lunch | dinner | both at purchase time.',
                max_length=10,
                null=True,
            ),
        ),
        migrations.RunPython(backfill_meal_period_snapshot, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='order',
            name='meal_period_snapshot',
            field=models.CharField(
                help_text='lunch | dinner | both at purchase time.',
                max_length=10,
            ),
        ),
    ]
