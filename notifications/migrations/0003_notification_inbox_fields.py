# Generated manually for notification inbox fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0002_pushcampaign_pushcampaignrecipient_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='notification',
            name='notification_type',
            field=models.CharField(blank=True, default='', max_length=50),
        ),
        migrations.AddField(
            model_name='notification',
            name='screen',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='notification',
            name='data',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AlterModelOptions(
            name='notification',
            options={'ordering': ['-created_at']},
        ),
    ]
