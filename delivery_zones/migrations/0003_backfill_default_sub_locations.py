# Data migration: default sub-location per location + customer backfill.

import uuid

from django.db import migrations


def forwards(apps, schema_editor):
    DeliveryLocation = apps.get_model('delivery_zones', 'DeliveryLocation')
    DeliverySubLocation = apps.get_model('delivery_zones', 'DeliverySubLocation')
    CustomerProfile = apps.get_model('user_management', 'CustomerProfile')

    location_to_default: dict[int, int] = {}
    for location in DeliveryLocation.objects.all().iterator():
        existing = (
            DeliverySubLocation.objects.filter(location_id=location.pk, is_default=True)
            .order_by('id')
            .first()
        )
        if existing is None:
            existing = DeliverySubLocation.objects.create(
                public_id=uuid.uuid4(),
                name=location.name,
                location_id=location.pk,
                priority=1,
                status='active',
                is_default=True,
            )
        location_to_default[location.pk] = existing.pk

    customers = CustomerProfile.objects.filter(
        delivery_location_id__isnull=False,
        delivery_sub_location_id__isnull=True,
    ).only('id', 'delivery_location_id')
    for customer in customers.iterator():
        default_id = location_to_default.get(customer.delivery_location_id)
        if default_id is None:
            continue
        CustomerProfile.objects.filter(pk=customer.pk).update(
            delivery_sub_location_id=default_id
        )


def backwards(apps, schema_editor):
    DeliverySubLocation = apps.get_model('delivery_zones', 'DeliverySubLocation')
    CustomerProfile = apps.get_model('user_management', 'CustomerProfile')
    CustomerProfile.objects.filter(delivery_sub_location_id__isnull=False).update(
        delivery_sub_location_id=None
    )
    DeliverySubLocation.objects.filter(is_default=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('delivery_zones', '0002_delivery_sub_locations'),
        ('user_management', '0024_delivery_sub_locations'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
