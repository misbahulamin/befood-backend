# Generated manually for subscription-meal-preference-delivery-fee

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0018_customersubscription_cancel_audit'),
    ]

    operations = [
        migrations.AddField(
            model_name='customersubscription',
            name='quantity',
            field=models.PositiveIntegerField(
                default=1,
                help_text='Canonical person/serving quantity for this subscription (min 1).',
            ),
        ),
        migrations.AlterField(
            model_name='customersubscription',
            name='meal_period_snapshot',
            field=models.CharField(
                help_text=(
                    'Effective subscription meal preference (lunch | dinner | both). '
                    'Persisted selection validated against the package coverage at '
                    'subscribe time; drives all subscription delivery generation.'
                ),
                max_length=10,
            ),
        ),
    ]
