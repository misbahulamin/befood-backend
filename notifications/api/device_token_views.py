from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from notifications.services.device_service import register_device_token, deactivate_device_token

from .openapi import (
    DEVICE_TOKEN_REGISTER_REQUEST,
    DEVICE_TOKEN_REGISTER_SUCCESS,
    DEVICE_TOKEN_REMOVE_REQUEST,
    DEVICE_TOKEN_REMOVE_SUCCESS,
    NOTIFICATIONS_TAG,
)
from .serializers import (
    DeviceTokenRegisterSerializer,
    DeviceTokenRemoveSerializer,
    DeviceTokenSuccessResponseSerializer,
)


class DeviceTokenRegisterView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=[NOTIFICATIONS_TAG],
        request=DeviceTokenRegisterSerializer,
        responses={200: DeviceTokenSuccessResponseSerializer},
        examples=[
            OpenApiExample(
                'Register Android device',
                value=DEVICE_TOKEN_REGISTER_REQUEST,
                request_only=True,
            ),
        ],
        description='Register or refresh an FCM device token for the authenticated user.',
    )
    def post(self, request):
        serializer = DeviceTokenRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        register_device_token(
            user=request.user,
            token=serializer.validated_data['token'],
            platform=serializer.validated_data['platform'],
            device_name=serializer.validated_data.get('device_name', ''),
            app_version=serializer.validated_data.get('app_version', ''),
        )
        return Response(DEVICE_TOKEN_REGISTER_SUCCESS, status=status.HTTP_200_OK)


class DeviceTokenRemoveView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=[NOTIFICATIONS_TAG],
        request=DeviceTokenRemoveSerializer,
        responses={200: DeviceTokenSuccessResponseSerializer},
        examples=[
            OpenApiExample(
                'Deactivate device token',
                value=DEVICE_TOKEN_REMOVE_REQUEST,
                request_only=True,
            ),
        ],
        description='Soft-deactivate an FCM device token owned by the authenticated user.',
    )
    def post(self, request):
        serializer = DeviceTokenRemoveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        deactivated = deactivate_device_token(
            user=request.user,
            token=serializer.validated_data['token'],
        )
        if not deactivated:
            return Response({'detail': 'Device token not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(DEVICE_TOKEN_REMOVE_SUCCESS, status=status.HTTP_200_OK)
