from django.contrib.auth.models import User
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from user_management.api.deliveryman_serializers import (
    AdminDeliverymanListSerializer,
    AdminDeliverymanRejectSerializer,
    AdminDeliverymanVerifiedStatusSerializer,
    DeliverymanCurrentUserSerializer,
    DeliverymanLoginSerializer,
    DeliverymanRegistrationSerializer,
    DeliverymanResendVerificationSerializer,
)
from user_management.api.permissions import IsVerifiedAdmin, IsVerifiedDeliveryman
from user_management.filters import RiderProfileFilter
from user_management.models import RiderProfile
from user_management.services.deliveryman_auth import (
    approve_deliveryman,
    get_deliveryman_login_response,
    register_deliveryman,
    reject_deliveryman,
    set_deliveryman_verified,
)
from user_management.services.deliveryman_email import (
    mark_deliveryman_email_verified,
    send_deliveryman_activation_email,
    verify_deliveryman_token,
)
from user_management.services.email_verification import get_user_from_uid


class DeliverymanRegistrationView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=['Delivery Man Auth'],
        request=DeliverymanRegistrationSerializer,
        responses={201: OpenApiResponse(response=None, description='Registration successful')},
        examples=[
            OpenApiExample(
                'Success',
                value={
                    'message': 'Registration successful. Please check your email to verify your account.',
                    'email': 'rider@example.com',
                },
            )
        ],
        description='Register a new Delivery Man account and send verification email.',
    )
    def post(self, request):
        serializer = DeliverymanRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user, _ = register_deliveryman(serializer.validated_data, request)
        return Response(
            {
                'message': 'Registration successful. Please check your email to verify your account.',
                'email': user.email,
            },
            status=status.HTTP_201_CREATED,
        )


class DeliverymanVerifyEmailView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(tags=['Delivery Man Auth'], description='Verify Delivery Man email using uid and token.')
    def get(self, request, uidb64, token):
        user = get_user_from_uid(uidb64)
        if not user or not hasattr(user, 'rider_profile'):
            return Response({'detail': 'Invalid or expired verification link.'}, status=status.HTTP_400_BAD_REQUEST)
        if user.rider_profile.is_email_verified:
            return Response({'message': 'Email is already verified.'}, status=status.HTTP_200_OK)
        if not verify_deliveryman_token(user, token):
            return Response({'detail': 'Invalid or expired verification link.'}, status=status.HTTP_400_BAD_REQUEST)
        mark_deliveryman_email_verified(user.rider_profile)
        return Response(
            {
                'message': (
                    'Email verified successfully. '
                    'Your account is pending admin approval before you can login.'
                )
            }
        )


class DeliverymanResendVerificationView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=['Delivery Man Auth'],
        request=DeliverymanResendVerificationSerializer,
        description='Resend the verification email for an unverified Delivery Man account.',
    )
    def post(self, request):
        serializer = DeliverymanResendVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User.objects.filter(email__iexact=serializer.validated_data['email']).first()
        if not user or not hasattr(user, 'rider_profile'):
            return Response({'message': 'If the account exists, verification instructions will be sent.'})
        if user.rider_profile.is_email_verified:
            return Response({'message': 'This email is already verified.'})
        send_deliveryman_activation_email(request, user)
        return Response({'message': 'Verification email has been sent again.'})


class DeliverymanLoginView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=['Delivery Man Auth'],
        request=DeliverymanLoginSerializer,
        description='Login Delivery Man using email and password (requires email verification and admin approval).',
    )
    def post(self, request):
        serializer = DeliverymanLoginSerializer(data=request.data)
        if not serializer.is_valid():
            errors = serializer.errors
            if 'non_field_errors' in errors and errors['non_field_errors']:
                detail = errors['non_field_errors'][0]
                return Response({'detail': str(detail)}, status=status.HTTP_400_BAD_REQUEST)
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)
        response_data = get_deliveryman_login_response(serializer.validated_data['user'])
        return Response(response_data)


class DeliverymanCurrentUserView(APIView):
    permission_classes = [IsVerifiedDeliveryman]

    @extend_schema(tags=['Delivery Man Auth'], description='Get current authenticated Delivery Man information.')
    def get(self, request):
        serializer = DeliverymanCurrentUserSerializer(request.user)
        return Response(serializer.data)


class AdminDeliverymanPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


@extend_schema_view(
    list=extend_schema(
        tags=['Admin Delivery Men'],
        summary='List Delivery Man accounts',
        description=(
            'Verified admin only. Default pending queue: email-verified and approval_status=pending. '
            'Pass pending_only=false (or filter explicitly) to browse all statuses.'
        ),
        parameters=[
            OpenApiParameter(
                name='pending_only',
                type=bool,
                location=OpenApiParameter.QUERY,
                description='When true (default), only email-verified pending accounts. Set false to list all.',
            ),
            OpenApiParameter(name='approval_status', type=str, location=OpenApiParameter.QUERY),
            OpenApiParameter(name='is_email_verified', type=bool, location=OpenApiParameter.QUERY),
            OpenApiParameter(name='is_verified', type=bool, location=OpenApiParameter.QUERY),
            OpenApiParameter(name='search', type=str, location=OpenApiParameter.QUERY),
        ],
    ),
    retrieve=extend_schema(tags=['Admin Delivery Men'], summary='Delivery Man detail by public_id'),
)
class AdminDeliverymanViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsVerifiedAdmin]
    serializer_class = AdminDeliverymanListSerializer
    pagination_class = AdminDeliverymanPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = RiderProfileFilter
    lookup_field = 'public_id'
    lookup_url_kwarg = 'public_id'
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_queryset(self):
        qs = RiderProfile.objects.select_related('user').order_by('-created_at', '-id')
        pending_only = self.request.query_params.get('pending_only', 'true').lower()
        # Only apply default pending queue on list when no explicit approval_status filter.
        if (
            self.action == 'list'
            and pending_only not in ('false', '0', 'no')
            and 'approval_status' not in self.request.query_params
        ):
            qs = qs.filter(
                is_email_verified=True,
                approval_status=RiderProfile.ApprovalStatus.PENDING,
            )
        return qs

    @extend_schema(
        tags=['Admin Delivery Men'],
        request=None,
        responses={200: AdminDeliverymanListSerializer},
        description='Approve an email-verified pending Delivery Man.',
    )
    @action(detail=True, methods=['post'], url_path='approve')
    def approve(self, request, public_id=None):
        profile = self.get_object()
        try:
            approve_deliveryman(profile, send_email=True)
        except ValidationError as exc:
            return Response(exc.detail, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        profile.refresh_from_db()
        return Response(AdminDeliverymanListSerializer(profile).data)

    @extend_schema(
        tags=['Admin Delivery Men'],
        request=AdminDeliverymanRejectSerializer,
        responses={200: AdminDeliverymanListSerializer},
        description='Reject a Delivery Man account.',
    )
    @action(detail=True, methods=['post'], url_path='reject')
    def reject(self, request, public_id=None):
        profile = self.get_object()
        serializer = AdminDeliverymanRejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reject_deliveryman(profile, reason=serializer.validated_data.get('reason', ''), send_email=True)
        profile.refresh_from_db()
        return Response(AdminDeliverymanListSerializer(profile).data)

    @extend_schema(
        tags=['Admin Delivery Men'],
        request=AdminDeliverymanVerifiedStatusSerializer,
        responses={200: AdminDeliverymanListSerializer},
        description='Set or revoke verified status for operational corrections.',
    )
    @action(detail=True, methods=['patch'], url_path='verified-status')
    def verified_status(self, request, public_id=None):
        profile = self.get_object()
        serializer = AdminDeliverymanVerifiedStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        notes = serializer.validated_data.get('admin_notes')
        try:
            set_deliveryman_verified(
                profile,
                serializer.validated_data['is_verified'],
                admin_notes=notes if 'admin_notes' in serializer.validated_data else None,
                send_email=serializer.validated_data['is_verified'],
            )
        except ValidationError as exc:
            return Response(exc.detail, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        profile.refresh_from_db()
        return Response(AdminDeliverymanListSerializer(profile).data)
