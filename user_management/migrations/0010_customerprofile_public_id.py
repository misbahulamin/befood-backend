import uuid

from django.db import migrations, models


def backfill_customer_public_ids(apps, schema_editor):
    CustomerProfile = apps.get_model('user_management', 'CustomerProfile')
    for row in CustomerProfile.objects.filter(public_id__isnull=True).iterator():
        row.public_id = uuid.uuid4()
        row.save(update_fields=['public_id'])


class Migration(migrations.Migration):

    dependencies = [
        ('user_management', '0009_deliveryman_auth_rider_profile'),
    ]

    operations = [
        migrations.AddField(
            model_name='customerprofile',
            name='public_id',
            field=models.UUIDField(editable=False, null=True),
        ),
        migrations.RunPython(backfill_customer_public_ids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='customerprofile',
            name='public_id',
            field=models.UUIDField(
                db_index=True,
                default=uuid.uuid4,
                editable=False,
                unique=True,
            ),
        ),
    ]
