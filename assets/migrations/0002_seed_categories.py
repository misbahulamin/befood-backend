from django.db import migrations

DEFAULT_CATEGORIES = [
    ('Kitchen Equipment', 'Refrigerators, burners, stoves, cookware, rice cookers, and similar kitchen durables.'),
    ('Furniture', 'Tables, chairs, shelves, and office/kitchen furniture.'),
    ('Lighting', 'Lights and lighting fixtures.'),
    ('Computer Equipment', 'Computers, monitors, printers, and related electronics.'),
    ('Other', 'Other permanent non-consumable items.'),
]


def seed_categories(apps, schema_editor):
    AssetCategory = apps.get_model('assets', 'AssetCategory')
    for name, description in DEFAULT_CATEGORIES:
        AssetCategory.objects.get_or_create(
            name=name,
            defaults={
                'description': description,
                'is_active': True,
            },
        )


def unseed_categories(apps, schema_editor):
    AssetCategory = apps.get_model('assets', 'AssetCategory')
    names = [name for name, _ in DEFAULT_CATEGORIES]
    AssetCategory.objects.filter(name__in=names).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('assets', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_categories, unseed_categories),
    ]
