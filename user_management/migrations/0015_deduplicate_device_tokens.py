from django.db import migrations


def deduplicate_device_tokens(apps, schema_editor):
    DeviceToken = apps.get_model('user_management', 'DeviceToken')
    seen = {}
    duplicates = []

    for row in DeviceToken.objects.order_by('token', '-created_at').iterator():
        if row.token in seen:
            duplicates.append(row.pk)
        else:
            seen[row.token] = row.pk

    if duplicates:
        DeviceToken.objects.filter(pk__in=duplicates).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('user_management', '0014_customer_location_management'),
    ]

    operations = [
        migrations.RunPython(deduplicate_device_tokens, migrations.RunPython.noop),
    ]
