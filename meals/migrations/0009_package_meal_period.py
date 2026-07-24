from django.db import migrations, models


def backfill_meal_period(apps, schema_editor):
    MealCategory = apps.get_model('meals', 'MealCategory')
    MealCategory.objects.filter(meal_period__isnull=True).update(meal_period='both')
    MealCategory.objects.filter(meal_period='').update(meal_period='both')


class Migration(migrations.Migration):

    dependencies = [
        ('meals', '0008_monthly_menu_schedule'),
    ]

    operations = [
        migrations.AddField(
            model_name='mealcategory',
            name='meal_period',
            field=models.CharField(
                choices=[('lunch', 'Lunch'), ('dinner', 'Dinner'), ('both', 'Both')],
                help_text='Lunch only, dinner only, or both periods per service day.',
                max_length=10,
                null=True,
            ),
        ),
        migrations.RunPython(backfill_meal_period, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='mealcategory',
            name='meal_period',
            field=models.CharField(
                choices=[('lunch', 'Lunch'), ('dinner', 'Dinner'), ('both', 'Both')],
                default='both',
                help_text='Lunch only, dinner only, or both periods per service day.',
                max_length=10,
            ),
        ),
    ]
