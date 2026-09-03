from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from app_config.api.serializers import AppVersionSettingsSerializer
from app_config.services import get_app_version_settings, update_app_version_settings
from user_management.api.permissions import IsVerifiedAdmin


class PublicAppVersionView(APIView):
    """Unauthenticated mobile startup version policy."""

    permission_classes = [AllowAny]
    authentication_classes = []
    http_method_names = ['get', 'head', 'options']

    @extend_schema(
        tags=['App Config'],
        summary='Get mobile app version policy',
        description=(
            'Public. Returns latest and minimum supported app versions plus store URLs. '
            'Mobile clients compare installed semver locally to decide force/optional update.'
        ),
        responses={200: AppVersionSettingsSerializer},
        examples=[
            OpenApiExample(
                'Default policy',
                value={
                    'latest_version': '1.0.13',
                    'minimum_supported_version': '1.0.13',
                    'play_store_url': (
                        'https://play.google.com/store/apps/details?id=bd.com.befood'
                    ),
                    'app_store_url': '',
                    'updated_at': '2026-09-03T01:00:00Z',
                },
                response_only=True,
            ),
        ],
    )
    def get(self, request):
        settings_obj = get_app_version_settings()
        return Response(AppVersionSettingsSerializer(settings_obj).data)


class AdminAppVersionSettingsView(APIView):
    """Verified-admin read/update for mobile version policy."""

    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=['Admin App Config'],
        summary='Get app version settings',
        responses={
            200: AppVersionSettingsSerializer,
            403: OpenApiResponse(description='Admin required'),
        },
    )
    def get(self, request):
        settings_obj = get_app_version_settings()
        return Response(AppVersionSettingsSerializer(settings_obj).data)

    @extend_schema(
        tags=['Admin App Config'],
        summary='Update app version settings',
        request=AppVersionSettingsSerializer,
        responses={
            200: AppVersionSettingsSerializer,
            400: OpenApiResponse(description='Validation error'),
            403: OpenApiResponse(description='Admin required'),
        },
    )
    def patch(self, request):
        settings_obj = get_app_version_settings()
        serializer = AppVersionSettingsSerializer(
            settings_obj, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        updated = update_app_version_settings(
            latest_version=serializer.validated_data.get('latest_version'),
            minimum_supported_version=serializer.validated_data.get(
                'minimum_supported_version'
            ),
            play_store_url=serializer.validated_data.get('play_store_url'),
            app_store_url=serializer.validated_data.get('app_store_url'),
        )
        return Response(AppVersionSettingsSerializer(updated).data)
