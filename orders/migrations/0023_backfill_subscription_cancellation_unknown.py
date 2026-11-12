"""Backfill SubscriptionCancellation(reason_code=unknown) for existing cancels."""

from django.db import migrations


def forwards(apps, schema_editor):
    CustomerSubscription = apps.get_model('orders', 'CustomerSubscription')
    SubscriptionCancellation = apps.get_model('orders', 'SubscriptionCancellation')

    cancelled = CustomerSubscription.objects.filter(status='cancelled').exclude(
        cancellation__isnull=False,
    )
    rows = []
    for sub in cancelled.iterator(chunk_size=500):
        cancelled_by = sub.cancel_source or 'system'
        if cancelled_by not in ('customer', 'admin', 'system'):
            cancelled_by = 'system'
        rows.append(
            SubscriptionCancellation(
                subscription_id=sub.pk,
                customer_id=sub.customer_id,
                reason_code='unknown',
                reason_text='',
                cancelled_by=cancelled_by,
            )
        )
        if len(rows) >= 500:
            SubscriptionCancellation.objects.bulk_create(rows)
            rows = []
    if rows:
        SubscriptionCancellation.objects.bulk_create(rows)


def backwards(apps, schema_editor):
    SubscriptionCancellation = apps.get_model('orders', 'SubscriptionCancellation')
    SubscriptionCancellation.objects.filter(reason_code='unknown').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0022_subscription_cancellation_churn_follow_up'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
