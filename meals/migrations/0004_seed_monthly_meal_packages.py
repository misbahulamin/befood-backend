import base64
from decimal import Decimal

from django.core.files.base import ContentFile
from django.db import migrations

PLACEHOLDER_JPEG = base64.b64decode(
    '/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRof'
    'Hh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAARCAABAAEDASIAAhEBAxEB'
    '/8QAFQABAQAAAAAAAAAAAAAAAAAAAAv/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAA'
    'AAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwCdABmX/9k='
)

MEAL_PACKAGES = [
    {
        'meal_name': 'Student Package',
        'total_price': Decimal('2737.00'),
        'description': (
            'Affordable monthly meal plan for students with balanced daily meals '
            'at a budget-friendly price.'
        ),
    },
    {
        'meal_name': 'Regular Package',
        'total_price': Decimal('3480.00'),
        'description': (
            'Standard monthly meal plan with a variety of daily dishes suitable '
            'for everyday dining.'
        ),
    },
    {
        'meal_name': 'Premium Package',
        'total_price': Decimal('3987.00'),
        'description': (
            'Premium monthly meal plan with enhanced menu options and higher '
            'quality ingredients.'
        ),
    },
]


def seed_meal_packages(apps, schema_editor):
    MealCategory = apps.get_model('meals', 'MealCategory')

    for package in MEAL_PACKAGES:
        if MealCategory.objects.filter(meal_name=package['meal_name']).exists():
            continue

        meal = MealCategory(
            meal_name=package['meal_name'],
            total_price=package['total_price'],
            meal_type='monthly',
            description=package['description'],
            is_active=True,
        )
        filename = package['meal_name'].lower().replace(' ', '-') + '.jpg'
        meal.meal_thumbnail.save(filename, ContentFile(PLACEHOLDER_JPEG), save=True)


def remove_meal_packages(apps, schema_editor):
    MealCategory = apps.get_model('meals', 'MealCategory')
    names = [package['meal_name'] for package in MEAL_PACKAGES]
    MealCategory.objects.filter(meal_name__in=names).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('meals', '0003_alter_mealcategory_total_price'),
    ]

    operations = [
        migrations.RunPython(seed_meal_packages, remove_meal_packages),
    ]
