import uuid

from django.db import migrations, models


def backfill_public_ids(apps, schema_editor):
    MealCategory = apps.get_model('meals', 'MealCategory')
    for meal in MealCategory.objects.filter(public_id__isnull=True).iterator():
        meal.public_id = uuid.uuid4()
        meal.save(update_fields=['public_id'])


class Migration(migrations.Migration):

    dependencies = [
        ('meals', '0009_package_meal_period'),
    ]

    operations = [
        migrations.AddField(
            model_name='mealcategory',
            name='public_id',
            field=models.UUIDField(editable=False, null=True),
        ),
        migrations.RunPython(backfill_public_ids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='mealcategory',
            name='public_id',
            field=models.UUIDField(
                db_index=True,
                default=uuid.uuid4,
                editable=False,
                unique=True,
            ),
        ),
    ]
