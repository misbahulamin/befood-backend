from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from sliders.models import HomeSlider
from sliders.utils.slider_image import (
    validate_image_extension,
    validate_image_size,
)


def _absolute_image_url(obj, request):
    if not obj.image:
        return None
    url = obj.image.url
    return request.build_absolute_uri(url) if request else url


class PublicSliderSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = HomeSlider
        fields = ('public_id', 'image_url', 'priority')
        read_only_fields = fields

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_image_url(self, obj):
        return _absolute_image_url(obj, self.context.get('request'))


class AdminSliderSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()
    image = serializers.ImageField(required=False, allow_null=True)
    priority = serializers.IntegerField(min_value=1, default=1)

    class Meta:
        model = HomeSlider
        fields = (
            'public_id',
            'image',
            'image_url',
            'priority',
            'is_active',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('public_id', 'image_url', 'created_at', 'updated_at')

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_image_url(self, obj):
        return _absolute_image_url(obj, self.context.get('request'))

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['image_url'] = _absolute_image_url(
            instance, self.context.get('request'),
        )
        return data

    def validate_image(self, value):
        if value is None:
            return value
        try:
            validate_image_extension(value.name)
            validate_image_size(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        if value.content_type not in (
            'image/jpeg', 'image/png', 'image/webp',
        ):
            raise serializers.ValidationError(
                'Invalid image type. Allowed: jpg, jpeg, png, webp.',
            )
        try:
            from PIL import Image
            value.seek(0)
            with Image.open(value) as img:
                img.verify()
            value.seek(0)
        except Exception as exc:
            raise serializers.ValidationError(
                'Uploaded file is not a valid image.',
            ) from exc
        return value

    def validate(self, attrs):
        if self.instance is None and not attrs.get('image'):
            raise serializers.ValidationError(
                {'image': 'Image is required.'},
            )
        return attrs
