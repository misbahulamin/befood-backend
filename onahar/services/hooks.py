"""Integration helpers for order/refund flows to call Onahar safely."""

from onahar.services.contribution import credit_for_delivery, reverse_for_delivery


def onahar_on_delivery_delivered(delivery, actor=None):
    return credit_for_delivery(delivery, actor=actor)


def onahar_on_delivery_reversed(delivery, actor=None):
    """Call when a previously delivered meal is refunded/undone."""
    return reverse_for_delivery(delivery, actor=actor)
