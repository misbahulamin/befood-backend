import uuid

import django.utils.timezone
from django.db import migrations, models


def backfill_rider_public_ids(apps, schema_editor):
    RiderProfile = apps.get_model('user_management', 'RiderProfile')
    for row in RiderProfile.objects.filter(public_id__isnull=True).iterator():
        row.public_id = uuid.uuid4()
        row.save(update_fields=['public_id'])


class Migration(migrations.Migration):

    dependencies = [
        ('user_management', '0008_backfill_delivery_places_from_present'),
    ]

    operations = [
        migrations.AddField(
            model_name='riderprofile',
            name='public_id',
            field=models.UUIDField(editable=False, null=True),
        ),
        migrations.RunPython(backfill_rider_public_ids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='riderprofile',
            name='public_id',
            field=models.UUIDField(
                db_index=True,
                default=uuid.uuid4,
                editable=False,
                unique=True,
            ),
        ),
        migrations.AddField(
            model_name='riderprofile',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='riderprofile',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name='riderprofile',
            name='phone',
            field=models.CharField(blank=True, max_length=10, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='riderprofile',
            name='address',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='riderprofile',
            name='is_email_verified',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='riderprofile',
            name='email_verified_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='riderprofile',
            name='approval_status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pending'),
                    ('approved', 'Approved'),
                    ('rejected', 'Rejected'),
                ],
                default='pending',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='riderprofile',
            name='is_verified',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='riderprofile',
            name='verified_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='riderprofile',
            name='rejected_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='riderprofile',
            name='rejection_reason',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='riderprofile',
            name='admin_notes',
            field=models.TextField(blank=True),
        ),
    ]
