from __future__ import annotations

from django.db import transaction

from support.models import SupportConversation
from user_management.models import CustomerProfile


def get_or_create_conversation(customer: CustomerProfile) -> SupportConversation:
    conversation, _created = SupportConversation.objects.get_or_create(customer=customer)
    return conversation


def get_conversation_by_public_id(public_id) -> SupportConversation | None:
    return (
        SupportConversation.objects.select_related(
            'customer',
            'customer__user',
        )
        .filter(public_id=public_id)
        .first()
    )


@transaction.atomic
def update_conversation_status(
    conversation: SupportConversation,
    *,
    status: str,
) -> SupportConversation:
    if status not in SupportConversation.Status.values:
        raise ValueError(f'Invalid status: {status}')
    conversation.status = status
    conversation.save(update_fields=['status', 'updated_at'])
    return conversation


def admin_conversations_queryset():
    return SupportConversation.objects.select_related(
        'customer',
        'customer__user',
    ).all()


def apply_admin_conversation_filters(qs, *, status: str | None = None, has_unread=None, q: str | None = None):
    if status:
        qs = qs.filter(status=status)
    if has_unread is True:
        qs = qs.filter(admin_unread_count__gt=0)
    elif has_unread is False:
        qs = qs.filter(admin_unread_count=0)
    if q:
        q = q.strip()
        if q:
            from django.db.models import Q

            qs = qs.filter(
                Q(customer__user__first_name__icontains=q)
                | Q(customer__user__last_name__icontains=q)
                | Q(customer__user__username__icontains=q)
                | Q(customer__user__email__icontains=q)
                | Q(customer__phone__icontains=q)
                | Q(last_message__icontains=q)
            )
    return qs.order_by('-last_message_at', '-id')
