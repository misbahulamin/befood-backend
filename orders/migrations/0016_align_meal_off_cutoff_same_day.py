import datetime

from django.db import migrations, models


def forwards_migrate_legacy_defaults(apps, schema_editor):
    MealOffSettings = apps.get_model('orders', 'MealOffSettings')
    legacy_lunch = datetime.time(23, 59)
    legacy_dinner = datetime.time(14, 0)
    new_lunch = datetime.time(0, 0)
    new_dinner = datetime.time(16, 0)
    MealOffSettings.objects.filter(
        pk=1,
        lunch_off_time=legacy_lunch,
        dinner_off_time=legacy_dinner,
    ).update(lunch_off_time=new_lunch, dinner_off_time=new_dinner)


def backwards_restore_legacy_defaults(apps, schema_editor):
    MealOffSettings = apps.get_model('orders', 'MealOffSettings')
    legacy_lunch = datetime.time(23, 59)
    legacy_dinner = datetime.time(14, 0)
    new_lunch = datetime.time(0, 0)
    new_dinner = datetime.time(16, 0)
    MealOffSettings.objects.filter(
        pk=1,
        lunch_off_time=new_lunch,
        dinner_off_time=new_dinner,
    ).update(lunch_off_time=legacy_lunch, dinner_off_time=legacy_dinner)


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0015_orderwalletsettings_balance_thresholds'),
    ]

    operations = [
        migrations.AlterField(
            model_name='mealoffsettings',
            name='lunch_off_time',
            field=models.TimeField(
                default=datetime.time(0, 0),
                help_text='Deadline time on the lunch service date.',
            ),
        ),
        migrations.AlterField(
            model_name='mealoffsettings',
            name='dinner_off_time',
            field=models.TimeField(
                default=datetime.time(16, 0),
                help_text='Deadline time on the dinner service date.',
            ),
        ),
        migrations.RunPython(
            forwards_migrate_legacy_defaults,
            backwards_restore_legacy_defaults,
        ),
    ]
