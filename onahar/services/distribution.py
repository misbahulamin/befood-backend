from django.db import transaction
from django.utils import timezone

from onahar.models import OnaharDistribution, OnaharDistributionMedia, OnaharFundLedgerEntry
from onahar.services.audit import write_audit
from onahar.services.fund import InsufficientOnaharFundError, credit_fund, debit_fund


class OnaharDistributionError(Exception):
    def __init__(self, message: str, code: str = 'ONAHAR_DISTRIBUTION_ERROR'):
        super().__init__(message)
        self.code = code


ALLOWED_IMAGE_CONTENT_TYPES = {
    'image/jpeg',
    'image/png',
    'image/webp',
    'image/gif',
}
MAX_IMAGE_BYTES = 5 * 1024 * 1024


def _validate_image(image_file):
    content_type = getattr(image_file, 'content_type', None) or ''
    if content_type and content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
        raise OnaharDistributionError(
            f'Unsupported image type: {content_type}',
            code='INVALID_MEDIA_TYPE',
        )
    size = getattr(image_file, 'size', None)
    if size is not None and size > MAX_IMAGE_BYTES:
        raise OnaharDistributionError(
            'Image exceeds maximum size of 5MB.',
            code='MEDIA_TOO_LARGE',
        )


@transaction.atomic
def create_distribution(*, data: dict, actor) -> OnaharDistribution:
    dist = OnaharDistribution.objects.create(
        title=data['title'],
        location=data['location'],
        full_address=data.get('full_address', ''),
        distribution_date=data['distribution_date'],
        meals_distributed=data['meals_distributed'],
        description=data.get('description', ''),
        beneficiary_info=data.get('beneficiary_info', ''),
        status=OnaharDistribution.Status.DRAFT,
        created_by=actor,
    )
    write_audit(
        action='distribution_created',
        actor=actor,
        new_value={
            'public_id': str(dist.public_id),
            'title': dist.title,
            'meals_distributed': dist.meals_distributed,
            'status': dist.status,
        },
    )
    return dist


@transaction.atomic
def update_draft_distribution(distribution: OnaharDistribution, *, data: dict, actor) -> OnaharDistribution:
    locked = OnaharDistribution.objects.select_for_update().get(pk=distribution.pk)
    if locked.status != OnaharDistribution.Status.DRAFT:
        raise OnaharDistributionError(
            'Only draft distributions can be edited.',
            code='DISTRIBUTION_NOT_DRAFT',
        )
    previous = {
        'title': locked.title,
        'location': locked.location,
        'meals_distributed': locked.meals_distributed,
    }
    for field in (
        'title',
        'location',
        'full_address',
        'distribution_date',
        'meals_distributed',
        'description',
        'beneficiary_info',
    ):
        if field in data and data[field] is not None:
            setattr(locked, field, data[field])
    locked.save()
    write_audit(
        action='distribution_edited',
        actor=actor,
        previous_value=previous,
        new_value={
            'title': locked.title,
            'location': locked.location,
            'meals_distributed': locked.meals_distributed,
        },
        metadata={'public_id': str(locked.public_id)},
    )
    return locked


@transaction.atomic
def attach_media(distribution: OnaharDistribution, *, image, actor, caption: str = '', sort_order: int = 0):
    locked = OnaharDistribution.objects.select_for_update().get(pk=distribution.pk)
    if locked.status == OnaharDistribution.Status.CANCELLED:
        raise OnaharDistributionError('Cannot add media to a cancelled distribution.')
    _validate_image(image)
    media = OnaharDistributionMedia.objects.create(
        distribution=locked,
        image=image,
        caption=caption or '',
        sort_order=sort_order,
        uploaded_by=actor,
    )
    write_audit(
        action='media_uploaded',
        actor=actor,
        new_value={
            'distribution_public_id': str(locked.public_id),
            'media_public_id': str(media.public_id),
        },
    )
    return media


@transaction.atomic
def publish_distribution(distribution: OnaharDistribution, *, actor) -> OnaharDistribution:
    locked = OnaharDistribution.objects.select_for_update().get(pk=distribution.pk)
    if locked.status == OnaharDistribution.Status.PUBLISHED:
        return locked
    if locked.status != OnaharDistribution.Status.DRAFT:
        raise OnaharDistributionError(
            f'Cannot publish distribution in status {locked.status}.',
            code='INVALID_STATUS',
        )
    try:
        debit_fund(
            meals=locked.meals_distributed,
            entry_type=OnaharFundLedgerEntry.EntryType.DISTRIBUTION,
            distribution=locked,
            note=f'Distribution {locked.public_id}',
            actor=actor,
            audit_action='fund_deducted',
        )
    except InsufficientOnaharFundError as exc:
        raise OnaharDistributionError(str(exc), code=exc.code) from exc

    locked.status = OnaharDistribution.Status.PUBLISHED
    locked.published_by = actor
    locked.published_at = timezone.now()
    locked.save(
        update_fields=['status', 'published_by', 'published_at', 'updated_at']
    )
    write_audit(
        action='distribution_published',
        actor=actor,
        new_value={
            'public_id': str(locked.public_id),
            'meals_distributed': locked.meals_distributed,
        },
    )
    return locked


@transaction.atomic
def cancel_distribution(distribution: OnaharDistribution, *, actor) -> OnaharDistribution:
    locked = OnaharDistribution.objects.select_for_update().get(pk=distribution.pk)
    if locked.status == OnaharDistribution.Status.CANCELLED:
        return locked
    if locked.status == OnaharDistribution.Status.DRAFT:
        locked.status = OnaharDistribution.Status.CANCELLED
        locked.cancelled_by = actor
        locked.cancelled_at = timezone.now()
        locked.save(
            update_fields=['status', 'cancelled_by', 'cancelled_at', 'updated_at']
        )
        write_audit(
            action='distribution_cancelled',
            actor=actor,
            new_value={'public_id': str(locked.public_id), 'was': 'draft'},
        )
        return locked
    if locked.status != OnaharDistribution.Status.PUBLISHED:
        raise OnaharDistributionError('Only published or draft distributions can be cancelled.')

    credit_fund(
        meals=locked.meals_distributed,
        entry_type=OnaharFundLedgerEntry.EntryType.DISTRIBUTION_RESTORE,
        distribution=locked,
        note=f'Restore after cancel {locked.public_id}',
        actor=actor,
        audit_action='fund_restored',
    )
    locked.status = OnaharDistribution.Status.CANCELLED
    locked.cancelled_by = actor
    locked.cancelled_at = timezone.now()
    locked.save(
        update_fields=['status', 'cancelled_by', 'cancelled_at', 'updated_at']
    )
    write_audit(
        action='distribution_cancelled',
        actor=actor,
        new_value={
            'public_id': str(locked.public_id),
            'meals_restored': locked.meals_distributed,
        },
    )
    return locked
