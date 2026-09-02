from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user_management', '0016_extend_device_token'),
    ]

    operations = [
        migrations.AddField(
            model_name='customerprofile',
            name='meal_service_blocked_low_balance',
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text='When true, automated meal delivery is blocked until wallet balance recovers.',
            ),
        ),
        migrations.AddField(
            model_name='customerprofile',
            name='meal_service_blocked_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='customerprofile',
            name='last_low_balance_reminder_on',
            field=models.DateField(
                blank=True,
                help_text='Asia/Dhaka business date of the last low-balance reminder (push/email).',
                null=True,
            ),
        ),
    ]
