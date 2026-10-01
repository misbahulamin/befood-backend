# Generated manually for admin-subscription-cancellation

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0017_deliveryman_360_logistics'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='customersubscription',
            name='cancel_source',
            field=models.CharField(
                blank=True,
                choices=[
                    ('customer', 'Customer'),
                    ('admin', 'Admin'),
                    ('system', 'System'),
                ],
                help_text='Who initiated cancel: customer | admin | system.',
                max_length=20,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='customersubscription',
            name='cancelled_by',
            field=models.ForeignKey(
                blank=True,
                help_text='User who cancelled (customer or admin actor when recorded).',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='cancelled_subscriptions',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
