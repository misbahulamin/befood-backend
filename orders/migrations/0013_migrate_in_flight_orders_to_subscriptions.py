from django.db import migrations


def forwards(apps, schema_editor):
    from orders.services.subscription_migration import migrate_in_flight_orders

    migrate_in_flight_orders()


def backwards(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('orders', '0012_subscription_based_meal_service'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
