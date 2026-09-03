import re

from rest_framework import serializers

from app_config.models import AppVersionSettings

_SEMVER_RE = re.compile(r'^\d+\.\d+\.\d+$')


def _validate_semver(value: str) -> str:
    if not _SEMVER_RE.match(value.strip()):
        raise serializers.ValidationError(
            'Version must be semver X.Y.Z (digits only, e.g. 1.0.13).'
        )
    return value.strip()


class AppVersionSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = AppVersionSettings
        fields = (
            'latest_version',
            'minimum_supported_version',
            'play_store_url',
            'app_store_url',
            'updated_at',
        )
        read_only_fields = ('updated_at',)

    def validate_latest_version(self, value: str) -> str:
        return _validate_semver(value)

    def validate_minimum_supported_version(self, value: str) -> str:
        return _validate_semver(value)
