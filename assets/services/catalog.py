"""
Permanent asset catalog services.

Domain only — no Request/Response, no meal/ingredient/order imports.
"""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import QuerySet

from assets.models import AssetCategory, PermanentAsset


def normalize_asset_tag(tag: str) -> str:
    """Trim whitespace; keep original case for display uniqueness."""
    return (tag or '').strip()


def active_categories(*, include_inactive: bool = False) -> QuerySet[AssetCategory]:
    qs = AssetCategory.objects.all()
    if not include_inactive:
        qs = qs.filter(is_active=True)
    return qs.order_by('name')


def active_assets(*, include_inactive: bool = False) -> QuerySet[PermanentAsset]:
    qs = PermanentAsset.objects.select_related('category', 'outlet')
    if not include_inactive:
        qs = qs.filter(is_active=True)
    return qs.order_by('name', 'asset_tag')


@transaction.atomic
def create_category(**fields) -> AssetCategory:
    category = AssetCategory(**fields)
    category.full_clean()
    category.save()
    return category


@transaction.atomic
def update_category(category: AssetCategory, **fields) -> AssetCategory:
    for attr, value in fields.items():
        setattr(category, attr, value)
    category.full_clean()
    category.save()
    return category


@transaction.atomic
def soft_deactivate_category(category: AssetCategory) -> AssetCategory:
    """Soft-deactivate a category (REST DELETE)."""
    category.is_active = False
    category.full_clean()
    category.save(update_fields=['is_active', 'updated_at'])
    return category


@transaction.atomic
def create_asset(**fields) -> PermanentAsset:
    if 'asset_tag' in fields:
        fields['asset_tag'] = normalize_asset_tag(fields['asset_tag'])
    asset = PermanentAsset(**fields)
    asset.full_clean()
    asset.save()
    return asset


@transaction.atomic
def update_asset(asset: PermanentAsset, **fields) -> PermanentAsset:
    if 'asset_tag' in fields:
        fields['asset_tag'] = normalize_asset_tag(fields['asset_tag'])
    for attr, value in fields.items():
        setattr(asset, attr, value)
    asset.full_clean()
    asset.save()
    return asset


@transaction.atomic
def soft_retire_asset(asset: PermanentAsset) -> PermanentAsset:
    """
    Soft-retire an asset (REST DELETE).

    Sets is_active=False. If status is still in_service or under_maintenance,
    moves status to retired.
    """
    asset.is_active = False
    if asset.status in (
        PermanentAsset.Status.IN_SERVICE,
        PermanentAsset.Status.UNDER_MAINTENANCE,
    ):
        asset.status = PermanentAsset.Status.RETIRED
    asset.full_clean()
    asset.save(update_fields=['is_active', 'status', 'updated_at'])
    return asset


def assert_unique_asset_tag(tag: str, *, exclude_pk=None) -> None:
    normalized = normalize_asset_tag(tag)
    qs = PermanentAsset.objects.filter(asset_tag=normalized)
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    if qs.exists():
        raise ValidationError({'asset_tag': 'An asset with this tag already exists.'})
