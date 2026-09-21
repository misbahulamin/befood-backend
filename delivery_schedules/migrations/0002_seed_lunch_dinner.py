import datetime

from django.db import migrations


def seed_lunch_dinner(apps, schema_editor):
    DeliverySchedule = apps.get_model('delivery_schedules', 'DeliverySchedule')
    if DeliverySchedule.objects.exists():
        return
    DeliverySchedule.objects.bulk_create(
        [
            DeliverySchedule(
                name='Lunch',
                start_time=datetime.time(12, 30),
                end_time=datetime.time(14, 30),
                is_active=True,
                sort_order=1,
            ),
            DeliverySchedule(
                name='Dinner',
                start_time=datetime.time(19, 0),
                end_time=datetime.time(21, 0),
                is_active=True,
                sort_order=2,
            ),
        ]
    )


def unseed_lunch_dinner(apps, schema_editor):
    DeliverySchedule = apps.get_model('delivery_schedules', 'DeliverySchedule')
    DeliverySchedule.objects.filter(name__in=['Lunch', 'Dinner']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('delivery_schedules', '0001_initial_delivery_schedule'),
    ]

    operations = [
        migrations.RunPython(seed_lunch_dinner, unseed_lunch_dinner),
    ]
