from django.db import migrations


def forwards(apps, schema_editor):
    CustomerAddress = apps.get_model('user_management', 'CustomerAddress')
    CustomerDeliveryPlace = apps.get_model('user_management', 'CustomerDeliveryPlace')
    MealDeliveryPreference = apps.get_model('user_management', 'MealDeliveryPreference')

    defaults = CustomerAddress.objects.filter(
        address_type='present',
        is_default_delivery=True,
    ).select_related('customer_profile')

    for address in defaults.iterator():
        profile = address.customer_profile
        if CustomerDeliveryPlace.objects.filter(customer_profile=profile).exists():
            continue

        label = (address.area or '').strip() or 'Home'
        place = CustomerDeliveryPlace.objects.create(
            customer_profile=profile,
            label=label[:100],
            full_address=address.full_address,
            city=address.city or 'Dhaka',
            area=address.area or '',
            building_name=address.building_name or '',
            floor=address.floor or '',
            flat_number=address.flat_number or '',
            landmark=address.landmark or '',
            latitude=address.latitude,
            longitude=address.longitude,
            is_active=True,
        )
        MealDeliveryPreference.objects.update_or_create(
            customer_profile=profile,
            defaults={
                'lunch_place': place,
                'dinner_place': place,
            },
        )


def backwards(apps, schema_editor):
    # Keep migrated places; do not delete customer data on reverse.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('user_management', '0007_meal_delivery_addresses'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
