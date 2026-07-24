import uuid

from django.db import migrations, models


def backfill_public_ids(apps, schema_editor):
    Order = apps.get_model('orders', 'Order')
    OrderDelivery = apps.get_model('orders', 'OrderDelivery')
    for row in Order.objects.filter(public_id__isnull=True).iterator():
        row.public_id = uuid.uuid4()
        row.save(update_fields=['public_id'])
    for row in OrderDelivery.objects.filter(public_id__isnull=True).iterator():
        row.public_id = uuid.uuid4()
        row.save(update_fields=['public_id'])


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0005_customer_meal_off'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='public_id',
            field=models.UUIDField(editable=False, null=True),
        ),
        migrations.AddField(
            model_name='orderdelivery',
            name='public_id',
            field=models.UUIDField(editable=False, null=True),
        ),
        migrations.RunPython(backfill_public_ids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='order',
            name='public_id',
            field=models.UUIDField(
                db_index=True,
                default=uuid.uuid4,
                editable=False,
                unique=True,
            ),
        ),
        migrations.AlterField(
            model_name='orderdelivery',
            name='public_id',
            field=models.UUIDField(
                db_index=True,
                default=uuid.uuid4,
                editable=False,
                unique=True,
            ),
        ),
    ]
