from django.contrib.auth.models import User
from django.contrib.auth import login as django_login
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import HttpResponse
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import permissions, status
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.views import APIView

from ..services.admin_access import is_verified_admin
from ..services.auth_service import get_admin_login_response, get_login_response, register_customer
from ..services.auth_otp import AuthOTPError
from ..services.email_verification import (
    get_user_from_uid,
    mark_email_verified,
    send_activation_email,
    verify_email_with_otp,
    verify_token,
)
from ..services.password_reset import (
    PasswordResetError,
    confirm_password_reset,
    confirm_password_reset_otp,
    request_password_reset,
    validate_password_reset,
    validate_password_reset_otp,
)
from .serializers import (
    AdminCurrentUserSerializer,
    AdminLoginSerializer,
    CurrentUserSerializer,
    CustomerLoginSerializer,
    CustomerRegistrationSerializer,
    EmailOTPVerifySerializer,
    PasswordResetConfirmSerializer,
    PasswordResetOTPConfirmSerializer,
    PasswordResetOTPValidateSerializer,
    PasswordResetRequestSerializer,
    PasswordResetValidateSerializer,
    ResendVerificationSerializer,
)

EMAIL_NOT_VERIFIED_LOGIN_MESSAGE = (
    'Your account is not verified yet. Please check your email for the '
    'verification code or link.'
)


class CustomerRegistrationView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=['Customer Auth'],
        request=CustomerRegistrationSerializer,
        responses={201: OpenApiResponse(response=None, description='Registration successful')},
        examples=[
            OpenApiExample(
                'Minimal registration',
                value={'email': 'customer@example.com', 'password': 'StrongPassword123'},
                request_only=True,
            ),
            OpenApiExample(
                'Legacy registration fields (optional)',
                value={
                    'email': 'customer@example.com',
                    'password': 'StrongPassword123',
                    'first_name': 'Rahim',
                    'last_name': 'Uddin',
                    'phone': '1712345678',
                    'occupation': 'student',
                    'is_bachelor': True,
                },
                request_only=True,
            ),
            OpenApiExample(
                'Success',
                value={
                    'message': 'Registration successful. Please check your email to verify your account.',
                    'email': 'customer@example.com',
                },
                response_only=True,
            ),
        ],
        description=(
            'Register a new customer with email and password. '
            'Profile fields are optional during the compatibility window. '
            'Sends the existing verification email.'
        ),
    )
    def post(self, request):
        serializer = CustomerRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user, _ = register_customer(serializer.validated_data, request)
        return Response({'message': 'Registration successful. Please check your email to verify your account.', 'email': user.email}, status=status.HTTP_201_CREATED)


class VerifyEmailView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(tags=['Customer Auth'], description='Verify customer email using uid and token.')
    def get(self, request, uidb64, token):
        user = get_user_from_uid(uidb64)
        if not user:
            return Response({'detail': 'Invalid or expired verification link.'}, status=status.HTTP_400_BAD_REQUEST)
        if hasattr(user, 'customer_profile') and user.customer_profile.is_email_verified:
            return Response({'message': 'Email is already verified.'}, status=status.HTTP_200_OK)
        if not verify_token(user, token):
            return Response({'detail': 'Invalid or expired verification link.'}, status=status.HTTP_400_BAD_REQUEST)
        mark_email_verified(user.customer_profile)
        return Response({'message': 'Email verified successfully. You can now login.'})


class ResendVerificationView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=['Customer Auth'],
        request=ResendVerificationSerializer,
        description=(
            'Resend the verification email (OTP + link) for an unverified account. '
            'Respects OTP cooldown and hourly issue caps.'
        ),
    )
    def post(self, request):
        serializer = ResendVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User.objects.filter(email__iexact=serializer.validated_data['email']).first()
        if not user or not hasattr(user, 'customer_profile'):
            return Response({'message': 'If the account exists, verification instructions will be sent.'})
        if user.customer_profile.is_email_verified:
            return Response({'message': 'This email is already verified.'})
        send_activation_email(request, user)
        return Response({'message': 'Verification email has been sent again.'})


class VerifyEmailOTPView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=['Customer Auth'],
        request=EmailOTPVerifySerializer,
        description='Verify customer email using a 6-digit OTP from the activation email.',
    )
    def post(self, request):
        serializer = EmailOTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            message = verify_email_with_otp(
                serializer.validated_data['email'],
                serializer.validated_data['otp'],
            )
        except AuthOTPError as exc:
            return Response({'detail': exc.message}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'message': message})


class ResendVerificationOTPView(ResendVerificationView):
    """Alias of resend-verification for OTP-first clients."""

    @extend_schema(
        tags=['Customer Auth'],
        request=ResendVerificationSerializer,
        description='Alias of resend-verification: send OTP + link (cooldown/hourly caps apply).',
    )
    def post(self, request):
        return super().post(request)


class PasswordResetRequestView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=['Customer Auth'],
        request=PasswordResetRequestSerializer,
        responses={
            200: OpenApiResponse(
                response=None,
                description='Generic success (does not reveal whether the account exists).',
            ),
        },
        examples=[
            OpenApiExample(
                'Request reset',
                value={'email': 'customer@example.com'},
                request_only=True,
            ),
            OpenApiExample(
                'Success',
                value={
                    'message': (
                        'If an account exists for this email, '
                        'password reset instructions will be sent.'
                    ),
                },
                response_only=True,
            ),
        ],
        description=(
            'Request a branded password-reset email. '
            'Always returns a generic success message (anti-enumeration).'
        ),
    )
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = request_password_reset(serializer.validated_data['email'])
        return Response({'message': message})


class PasswordResetValidateView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=['Customer Auth'],
        request=PasswordResetValidateSerializer,
        responses={
            200: OpenApiResponse(
                response=None,
                description='Reset link uid+token is valid.',
            ),
            400: OpenApiResponse(
                response=None,
                description='Invalid or expired reset link.',
            ),
        },
        examples=[
            OpenApiExample(
                'Validate reset link',
                value={'uid': 'MQ', 'token': 'abc123-def456'},
                request_only=True,
            ),
            OpenApiExample(
                'Valid',
                value={'message': 'Password reset link is valid.'},
                response_only=True,
            ),
        ],
        description=(
            'Validate a password-reset uid+token from the email deep link '
            'before showing the new-password form. Does not change the password.'
        ),
    )
    def post(self, request):
        serializer = PasswordResetValidateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            message = validate_password_reset(
                serializer.validated_data['uid'],
                serializer.validated_data['token'],
            )
        except PasswordResetError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'message': message})


class PasswordResetConfirmView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=['Customer Auth'],
        request=PasswordResetConfirmSerializer,
        responses={
            200: OpenApiResponse(
                response=None,
                description='Password updated; client must login again.',
            ),
            400: OpenApiResponse(
                response=None,
                description='Invalid token, weak password, or password mismatch.',
            ),
        },
        examples=[
            OpenApiExample(
                'Confirm reset',
                value={
                    'uid': 'MQ',
                    'token': 'abc123-def456',
                    'new_password': 'NewStrongPassword123',
                    'confirm_password': 'NewStrongPassword123',
                },
                request_only=True,
            ),
            OpenApiExample(
                'Success',
                value={
                    'message': (
                        'Password has been reset successfully. You can now login.'
                    ),
                },
                response_only=True,
            ),
        ],
        description=(
            'Set a new password using uid+token from the email deep link. '
            'Invalidates prior DRF auth tokens. Does not return a new auth token; '
            'client must call login afterwards.'
        ),
    )
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            message = confirm_password_reset(
                serializer.validated_data['uid'],
                serializer.validated_data['token'],
                serializer.validated_data['new_password'],
            )
        except PasswordResetError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except DjangoValidationError as exc:
            return Response(
                {'new_password': list(exc.messages)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({'message': message})


class PasswordResetRequestOTPView(PasswordResetRequestView):
    """Alias of password-reset request for OTP-first clients."""

    @extend_schema(
        tags=['Customer Auth'],
        request=PasswordResetRequestSerializer,
        description=(
            'Alias of password-reset request. Sends OTP + link when allowed '
            '(anti-enumeration; cooldown/hourly caps apply).'
        ),
    )
    def post(self, request):
        return super().post(request)


class PasswordResetValidateOTPView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=['Customer Auth'],
        request=PasswordResetOTPValidateSerializer,
        description=(
            'UX-only check that a password-reset OTP is currently valid. '
            'Does not consume the OTP and does not authorize password change; '
            'confirm-otp must send the OTP again for independent verification.'
        ),
    )
    def post(self, request):
        serializer = PasswordResetOTPValidateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            message = validate_password_reset_otp(
                serializer.validated_data['email'],
                serializer.validated_data['otp'],
            )
        except AuthOTPError as exc:
            return Response({'detail': exc.message}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'message': message})


class PasswordResetConfirmOTPView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=['Customer Auth'],
        request=PasswordResetOTPConfirmSerializer,
        description=(
            'Set a new password using email + OTP. Independently re-verifies the OTP, '
            'consumes it, and invalidates DRF auth tokens. Does not return a new auth token.'
        ),
    )
    def post(self, request):
        serializer = PasswordResetOTPConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            message = confirm_password_reset_otp(
                serializer.validated_data['email'],
                serializer.validated_data['otp'],
                serializer.validated_data['new_password'],
            )
        except AuthOTPError as exc:
            return Response({'detail': exc.message}, status=status.HTTP_400_BAD_REQUEST)
        except DjangoValidationError as exc:
            return Response(
                {'new_password': list(exc.messages)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({'message': message})


class CustomerLoginView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=['Customer Auth'],
        request=CustomerLoginSerializer,
        description=(
            'Login customer using email and password. Unverified accounts receive a '
            'not-verified error and a verification email when cooldown allows.'
        ),
    )
    def post(self, request):
        serializer = CustomerLoginSerializer(data=request.data)
        if not serializer.is_valid():
            errors = serializer.errors
            if 'non_field_errors' in errors and errors['non_field_errors']:
                detail = errors['non_field_errors'][0]
                return Response({'detail': str(detail)}, status=status.HTTP_400_BAD_REQUEST)
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)
        if serializer.validated_data.get('email_not_verified'):
            user = serializer.validated_data['user']
            send_activation_email(request, user)
            return Response(
                {
                    'detail': EMAIL_NOT_VERIFIED_LOGIN_MESSAGE,
                    'code': 'email_not_verified',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        response_data = get_login_response(serializer.validated_data['user'])
        return Response(response_data)


class CurrentUserView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=['Customer Auth'], description='Get current authenticated customer information.')
    def get(self, request):
        user = request.user
        serializer = CurrentUserSerializer(user)
        return Response(serializer.data)


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=['Customer Auth'], description='Logout current user by deleting token.')
    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response({'message': 'Logged out successfully.'})


class AdminLoginView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=['Admin Auth'],
        request=AdminLoginSerializer,
        description='Login verified admin using email and password.',
    )
    def post(self, request):
        serializer = AdminLoginSerializer(data=request.data)
        if not serializer.is_valid():
            errors = serializer.errors
            if 'non_field_errors' in errors and errors['non_field_errors']:
                detail = errors['non_field_errors'][0]
                return Response({'detail': str(detail)}, status=status.HTTP_400_BAD_REQUEST)
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)
        response_data = get_admin_login_response(serializer.validated_data['user'])
        return Response(response_data)


class AdminCurrentUserView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=['Admin Auth'], description='Get current authenticated admin information.')
    def get(self, request):
        if not is_verified_admin(request.user):
            return Response({'detail': 'Admin access required.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = AdminCurrentUserSerializer(request.user)
        return Response(serializer.data)
