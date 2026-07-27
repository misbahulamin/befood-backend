from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from assets.models import AssetCategory, PermanentAsset
from assets.services import (
    create_asset,
    create_category,
    update_asset,
    update_category,
)
from business.models import Outlet


def _raise_drf(exc: DjangoValidationError) -> None:
    if hasattr(exc, 'message_dict'):
        raise serializers.ValidationError(exc.message_dict) from exc
    raise serializers.ValidationError({'detail': list(exc.messages)}) from exc


class AssetCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetCategory
        fields = (
            'public_id',
            'name',
            'description',
            'is_active',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('public_id', 'created_at', 'updated_at')

    def create(self, validated_data):
        try:
            return create_category(**validated_data)
        except DjangoValidationError as exc:
            _raise_drf(exc)

    def update(self, instance, validated_data):
        try:
            return update_category(instance, **validated_data)
        except DjangoValidationError as exc:
            _raise_drf(exc)


class AssetCategorySummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetCategory
        fields = ('public_id', 'name')
        read_only_fields = fields


class OutletSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Outlet
        fields = ('id', 'name')
        read_only_fields = fields


class PermanentAssetSerializer(serializers.ModelSerializer):
    category_public_id = serializers.UUIDField(write_only=True)
    category = AssetCategorySummarySerializer(read_only=True)
    outlet_id = serializers.IntegerField(
        write_only=True,
        required=False,
        allow_null=True,
    )
    outlet = OutletSummarySerializer(read_only=True)
    purchase_cost = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        allow_null=True,
        coerce_to_string=True,
    )

    class Meta:
        model = PermanentAsset
        fields = (
            'public_id',
            'name',
            'category_public_id',
            'category',
            'asset_tag',
            'status',
            'quantity',
            'serial_number',
            'brand',
            'model',
            'outlet_id',
            'outlet',
            'purchase_date',
            'purchase_cost',
            'currency',
            'warranty_until',
            'notes',
            'is_active',
            'created_at',
            'updated_at',
        )
        read_only_fields = (
            'public_id',
            'category',
            'outlet',
            'created_at',
            'updated_at',
        )

    def validate_category_public_id(self, value):
        try:
            return AssetCategory.objects.get(public_id=value, is_active=True)
        except AssetCategory.DoesNotExist as exc:
            raise serializers.ValidationError(
                'Category not found or inactive.'
            ) from exc

    def validate_outlet_id(self, value):
        if value is None:
            return None
        try:
            return Outlet.objects.get(pk=value)
        except Outlet.DoesNotExist as exc:
            raise serializers.ValidationError('Outlet not found.') from exc

    def validate_status(self, value):
        allowed = {c.value for c in PermanentAsset.Status}
        if value not in allowed:
            raise serializers.ValidationError(
                f'Invalid status. Allowed: {", ".join(sorted(allowed))}.'
            )
        return value

    def _prepare_fields(self, validated_data):
        fields = dict(validated_data)
        if 'category_public_id' in fields:
            fields['category'] = fields.pop('category_public_id')
        if 'outlet_id' in fields:
            fields['outlet'] = fields.pop('outlet_id')
        return fields

    def create(self, validated_data):
        fields = self._prepare_fields(validated_data)
        try:
            return create_asset(**fields)
        except DjangoValidationError as exc:
            _raise_drf(exc)

    def update(self, instance, validated_data):
        fields = self._prepare_fields(validated_data)
        try:
            return update_asset(instance, **fields)
        except DjangoValidationError as exc:
            _raise_drf(exc)
