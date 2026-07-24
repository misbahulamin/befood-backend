import uuid

from django.db import migrations, models


def backfill_address_public_ids(apps, schema_editor):
    CustomerAddress = apps.get_model('user_management', 'CustomerAddress')
    for row in CustomerAddress.objects.filter(public_id__isnull=True).iterator():
        row.public_id = uuid.uuid4()
        row.save(update_fields=['public_id'])


class Migration(migrations.Migration):

    dependencies = [
        ('user_management', '0005_adminprofile'),
    ]

    operations = [
        migrations.AddField(
            model_name='customeraddress',
            name='public_id',
            field=models.UUIDField(editable=False, null=True),
        ),
        migrations.RunPython(backfill_address_public_ids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='customeraddress',
            name='public_id',
            field=models.UUIDField(
                db_index=True,
                default=uuid.uuid4,
                editable=False,
                unique=True,
            ),
        ),
    ]
