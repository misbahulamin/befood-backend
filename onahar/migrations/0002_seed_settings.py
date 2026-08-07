from django.db import migrations


def seed_settings(apps, schema_editor):
    OnaharSettings = apps.get_model('onahar', 'OnaharSettings')
    if not OnaharSettings.objects.filter(pk=1).exists():
        OnaharSettings.objects.create(
            pk=1,
            contribution_target=50,
            total_contributed_meals=0,
            total_distributed_meals=0,
            available_meals=0,
        )


def unseed(apps, schema_editor):
    OnaharSettings = apps.get_model('onahar', 'OnaharSettings')
    OnaharSettings.objects.filter(pk=1).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('onahar', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_settings, unseed),
    ]
