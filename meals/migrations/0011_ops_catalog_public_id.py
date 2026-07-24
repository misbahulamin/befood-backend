import uuid

from django.db import migrations, models


MODELS = (
    'ingredient',
    'mealcycle',
    'mealcycleplan',
    'mealcycleplanline',
    'monthlymenuschedule',
)


def backfill(apps, schema_editor):
    model_names = (
        'Ingredient',
        'MealCycle',
        'MealCyclePlan',
        'MealCyclePlanLine',
        'MonthlyMenuSchedule',
    )
    for name in model_names:
        Model = apps.get_model('meals', name)
        for row in Model.objects.filter(public_id__isnull=True).iterator():
            row.public_id = uuid.uuid4()
            row.save(update_fields=['public_id'])


class Migration(migrations.Migration):

    dependencies = [
        ('meals', '0010_mealcategory_public_id'),
    ]

    operations = [
        *[
            migrations.AddField(
                model_name=model,
                name='public_id',
                field=models.UUIDField(editable=False, null=True),
            )
            for model in MODELS
        ],
        migrations.RunPython(backfill, migrations.RunPython.noop),
        *[
            migrations.AlterField(
                model_name=model,
                name='public_id',
                field=models.UUIDField(
                    db_index=True,
                    default=uuid.uuid4,
                    editable=False,
                    unique=True,
                ),
            )
            for model in MODELS
        ],
    ]
