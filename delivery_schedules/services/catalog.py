from django.db.models import QuerySet

from delivery_schedules.models import DeliverySchedule


def get_public_delivery_schedules() -> QuerySet[DeliverySchedule]:
    """Active schedules ordered for customer/marketing display."""
    return DeliverySchedule.objects.filter(is_active=True).order_by(
        'sort_order',
        'name',
        'id',
    )


def delete_delivery_schedule(schedule: DeliverySchedule) -> None:
    """Hard-delete a delivery schedule (no dependents in v1)."""
    schedule.delete()
