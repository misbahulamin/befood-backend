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
    resend_verification_email,
    send_activation_email,
    verify_email_link,
    verify_email_with_otp,
)
from ..services.password_reset import (
    PasswordResetError,
    confirm_password_reset,
    confirm_password_reset_otp,
    request_password_reset,
    validate_password_reset,
    validate_password_reset_otp,
)
from .permissions import HasCustomerProfile
from .serializers import (
    AdminCurrentUserSerializer,
    AdminLoginSerializer,
    CurrentUserSerializer,
    CustomerLoginSerializer,
    CustomerRegistrationSerializer,
    EmailCheckSerializer,
    EmailOTPVerifySerializer,
    FacebookOAuthLoginSerializer,
    GoogleOAuthLoginSerializer,
    LogoutSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetOTPConfirmSerializer,
    PasswordResetOTPValidateSerializer,
    PasswordResetRequestSerializer,
    PasswordResetValidateSerializer,
    PhoneAvailabilitySerializer,
    PhoneOtpSendSerializer,
    PhoneOtpVerifySerializer,
    ResendVerificationSerializer,
    SetPasswordSerializer,
)

EMAIL_NOT_VERIFIED_LOGIN_MESSAGE = (
    'Your account is not verified yet. Please check your email for the '
    'verification code or link.'
)
PASSWORD_SETUP_REQUIRED_MESSAGE = (
    'Your account was created with Google or Facebook. Set a password before '
    'signing in with email.'
)


class CustomerEmailCheckView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=['Customer Auth'],
        request=EmailCheckSerializer,
        description=(
            'Email-first lookup for unified auth UX. Returns status '
            '`exists` (with has_password / password_setup_required for verified emails), '
            '`pending` (resume verification), or `available` (start deferred registration). '
            'Does not create a user or issue a token.'
        ),
        responses={
            200: OpenApiResponse(
                description='Branch status for the normalized email.',
                examples=[
                    OpenApiExample(
                        'Existing customer with password',
                        value={
                            'email': 'customer@example.com',
                            'status': 'exists',
                            'has_password': True,
                            'password_setup_required': False,
                        },
                        response_only=True,
                    ),
                    OpenApiExample(
                        'Existing social customer without password',
                        value={
                            'email': 'social@example.com',
                            'status': 'exists',
                            'has_password': False,
                            'password_setup_required': True,
                        },
                        response_only=True,
                    ),
                    OpenApiExample(
                        'Pending registration',
                        value={'email': 'new@example.com', 'status': 'pending'},
                        response_only=True,
                    ),
                    OpenApiExample(
                        'Available',
                        value={'email': 'fresh@example.com', 'status': 'available'},
                        response_only=True,
                    ),
                ],
            ),
            400: OpenApiResponse(description='Invalid email.'),
        },
    )
    def post(self, request):
        from user_management.services.email_check import check_customer_email

        serializer = EmailCheckSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(check_customer_email(serializer.validated_data['email']))


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
            'Start customer registration with email and password. '
            'Creates a temporary pending registration only; the permanent '
            'User account is created after email verification succeeds. '
            'Profile fields are optional during the compatibility window. '
            'Sends the verification email (OTP + link).'
        ),
    )
    def post(self, request):
        serializer = CustomerRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        pending, _ = register_customer(serializer.validated_data, request)
        return Response(
            {
                'message': 'Registration successful. Please check your email to verify your account.',
                'email': pending.email,
            },
            status=status.HTTP_201_CREATED,
        )


class VerifyEmailView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=['Customer Auth'],
        description=(
            'Verify customer email using uid and token. '
            'For new signups this finalizes a pending registration into an active account. '
            'Legacy inactive unverified users are still supported.'
        ),
    )
    def get(self, request, uidb64, token):
        body, http_status = verify_email_link(uidb64, token)
        return Response(body, status=http_status)


class ResendVerificationView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=['Customer Auth'],
        request=ResendVerificationSerializer,
        description=(
            'Resend the verification email (OTP + link) for a pending registration '
            'or legacy unverified account. Respects OTP cooldown and hourly issue caps.'
        ),
    )
    def post(self, request):
        serializer = ResendVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = resend_verification_email(request, serializer.validated_data['email'])
        return Response(payload)


class VerifyEmailOTPView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=['Customer Auth'],
        request=EmailOTPVerifySerializer,
        description=(
            'Verify customer email using a 6-digit OTP from the activation email. '
            'On success, creates the permanent customer account from the pending registration.'
        ),
    )
    def post(self, request):
        serializer = EmailOTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            payload = verify_email_with_otp(
                serializer.validated_data['email'],
                serializer.validated_data['otp'],
            )
        except AuthOTPError as exc:
            return Response({'detail': exc.message}, status=status.HTTP_400_BAD_REQUEST)
        return Response(payload)


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
            'Login customer using email and password. Optional device_token + platform '
            'upsert the FCM token after success. Unverified legacy accounts receive a '
            'not-verified error and a verification email when cooldown allows. '
            'Pending-only emails (never verified) return invalid credentials.'
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
        if serializer.validated_data.get('password_setup_required'):
            return Response(
                {
                    'detail': PASSWORD_SETUP_REQUIRED_MESSAGE,
                    'code': 'password_setup_required',
                    'password_setup_required': True,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
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
        user = serializer.validated_data['user']
        response_data = get_login_response(
            user,
            device_token=serializer.validated_data.get('device_token'),
            platform=serializer.validated_data.get('platform'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            auth_provider='email',
        )
        return Response(response_data)


class SetPasswordView(APIView):
    """Authenticated: set or change customer password."""

    permission_classes = [HasCustomerProfile]

    @extend_schema(
        tags=['Customer Auth'],
        request=SetPasswordSerializer,
        description=(
            'Set a usable password while authenticated. Unusable-password accounts '
            '(social/phone) do not require current_password. Accounts that already '
            'have a usable password must supply current_password.'
        ),
        responses={
            200: OpenApiResponse(description='Password updated.'),
            400: OpenApiResponse(description='Validation failed.'),
            401: OpenApiResponse(description='Authentication required.'),
        },
    )
    def post(self, request):
        from user_management.services.set_password import SetPasswordError, set_customer_password

        serializer = SetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            set_customer_password(
                request.user,
                password=serializer.validated_data['password'],
                current_password=serializer.validated_data.get('current_password') or None,
            )
        except SetPasswordError as exc:
            return Response(
                {'detail': exc.message, 'code': exc.code},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {
                'message': 'Password updated successfully.',
                'has_password': True,
            }
        )


class PhoneAvailabilityCheckView(APIView):
    """Check whether a phone may receive OTP for bind or login — no SMS."""

    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=['Customer Auth'],
        request=PhoneAvailabilitySerializer,
        description=(
            'Pre-OTP phone availability. Pass context=bind (authenticated link) or '
            'context=login (anonymous phone OTP). Does not send SMS. '
            'If context is omitted: authenticated → bind, else → login.'
        ),
        responses={
            200: OpenApiResponse(description='Availability result.'),
            400: OpenApiResponse(description='Invalid phone or context.'),
        },
    )
    def post(self, request):
        from user_management.services.phone_availability import (
            CONTEXT_BIND,
            CONTEXT_LOGIN,
            PhoneAvailabilityError,
            check_phone_availability,
        )

        serializer = PhoneAvailabilitySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        context = (serializer.validated_data.get('context') or '').strip().lower()
        user = request.user if request.user and request.user.is_authenticated else None
        if not context:
            context = CONTEXT_BIND if user is not None else CONTEXT_LOGIN
        if context == CONTEXT_BIND and user is None:
            return Response(
                {'detail': 'Authentication required for bind context.', 'code': 'AUTH_REQUIRED'},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        try:
            result = check_phone_availability(
                serializer.validated_data['phone'],
                context=context,
                user=user,
            )
        except PhoneAvailabilityError as exc:
            return Response(
                {'detail': exc.message, 'code': exc.code},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(result)


class CurrentUserView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=['Customer Auth'],
        description=(
            'Get current authenticated customer information. Sessions do not idle-expire; '
            'tokens remain valid until logout or a security revoke event.'
        ),
    )
    def get(self, request):
        user = request.user
        serializer = CurrentUserSerializer(user)
        return Response(serializer.data)


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=['Customer Auth'],
        request=LogoutSerializer,
        description=(
            'Logout current session only. Other devices remain signed in. '
            'Optional device_token deactivates that FCM token.'
        ),
    )
    def post(self, request):
        from user_management.models import AuthSession
        from user_management.services.auth_session import revoke_auth_session

        serializer = LogoutSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)

        auth = request.auth
        if isinstance(auth, AuthSession):
            revoke_auth_session(auth)
        elif isinstance(auth, Token):
            auth.delete()
        else:
            # Fallback: revoke matching AuthSession by Authorization key if present.
            header = request.META.get('HTTP_AUTHORIZATION', '')
            if header.lower().startswith('token '):
                key = header.split(' ', 1)[1].strip()
                session = AuthSession.objects.filter(key=key, revoked_at__isnull=True).first()
                if session:
                    revoke_auth_session(session)
                else:
                    Token.objects.filter(key=key).delete()

        device_token = serializer.validated_data.get('device_token')
        if device_token:
            from notifications.services.device_service import deactivate_device_token

            deactivate_device_token(request.user, device_token)

        return Response({'message': 'Logged out successfully.'})


class LogoutAllView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=['Customer Auth'],
        description=(
            'Logout all sessions for the current user and deactivate all FCM device tokens.'
        ),
    )
    def post(self, request):
        from user_management.services.auth_session import force_logout_user

        force_logout_user(request.user)
        return Response({'message': 'Logged out from all devices successfully.'})


class PhoneOtpSendView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=['Customer Auth'],
        request=PhoneOtpSendSerializer,
        description=(
            'Send a phone OTP via SMS.NET.BD. Accepts BD formats 017… / +880… / 880…. '
            'Does not return the OTP code.'
        ),
        responses={
            200: OpenApiResponse(description='OTP sent (or cooldown/rate-limit messaging).'),
            400: OpenApiResponse(description='Invalid phone or SMS failure.'),
        },
    )
    def post(self, request):
        serializer = PhoneOtpSendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return _phone_otp_send_response(serializer.validated_data['phone'])


class PhoneOtpVerifyView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=['Customer Auth'],
        request=PhoneOtpVerifySerializer,
        description=(
            'Verify phone OTP and create-or-login a password-less customer. '
            'Returns the unified auth success envelope.'
        ),
    )
    def post(self, request):
        from user_management.services.phone_otp import PhoneOtpError, verify_phone_otp

        serializer = PhoneOtpVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            response_data = verify_phone_otp(
                serializer.validated_data['phone'],
                serializer.validated_data['otp'],
                device_token=serializer.validated_data.get('device_token'),
                platform=serializer.validated_data.get('platform'),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
            )
        except PhoneOtpError as exc:
            return Response({'detail': exc.message, 'code': exc.code}, status=status.HTTP_400_BAD_REQUEST)
        return Response(response_data)


def _phone_otp_send_response(raw_phone: str):
    from user_management.services.phone_otp import (
        OTP_COOLDOWN_MESSAGE,
        OTP_RATE_LIMITED_MESSAGE,
        PhoneOtpError,
        PhoneOtpIssueStatus,
        issue_phone_otp,
    )

    try:
        result = issue_phone_otp(raw_phone)
    except PhoneOtpError as exc:
        return Response({'detail': exc.message, 'code': exc.code}, status=status.HTTP_400_BAD_REQUEST)

    if result.status == PhoneOtpIssueStatus.COOLDOWN:
        return Response(
            {'detail': OTP_COOLDOWN_MESSAGE, 'code': 'OTP_COOLDOWN'},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )
    if result.status == PhoneOtpIssueStatus.RATE_LIMITED:
        return Response(
            {'detail': OTP_RATE_LIMITED_MESSAGE, 'code': 'OTP_RATE_LIMITED'},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )
    return Response({'message': 'OTP sent successfully.', 'phone': result.phone})


class PhoneOtpBindSendView(APIView):
    """Authenticated: send OTP to bind a phone to the current customer (no new User)."""

    permission_classes = [HasCustomerProfile]

    @extend_schema(
        tags=['Customer Auth'],
        request=PhoneOtpSendSerializer,
        description=(
            'Authenticated phone bind: send OTP to attach a verified phone to the '
            'current customer profile. Ownership is checked before SMS; conflict → 409.'
        ),
        responses={
            200: OpenApiResponse(description='OTP sent.'),
            400: OpenApiResponse(description='Invalid phone or SMS failure.'),
            401: OpenApiResponse(description='Authentication required.'),
            409: OpenApiResponse(description='Phone already linked to another account.'),
            429: OpenApiResponse(description='Cooldown or rate limit.'),
        },
    )
    def post(self, request):
        from user_management.services.phone_availability import assert_phone_available_for_bind
        from user_management.services.phone_otp import PhoneOtpError

        serializer = PhoneOtpSendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            assert_phone_available_for_bind(request.user, serializer.validated_data['phone'])
        except PhoneOtpError as exc:
            status_code = (
                status.HTTP_409_CONFLICT
                if exc.code == 'PHONE_CONFLICT'
                else status.HTTP_400_BAD_REQUEST
            )
            return Response({'detail': exc.message, 'code': exc.code}, status=status_code)
        return _phone_otp_send_response(serializer.validated_data['phone'])


class PhoneOtpBindVerifyView(APIView):
    """Authenticated: verify OTP and bind phone to current customer."""

    permission_classes = [HasCustomerProfile]

    @extend_schema(
        tags=['Customer Auth'],
        request=PhoneOtpVerifySerializer,
        description=(
            'Authenticated phone bind: verify OTP and set phone + is_phone_verified on the '
            'current profile. Does not create a second User. Conflict if phone owned elsewhere.'
        ),
        responses={
            200: OpenApiResponse(description='Unified auth success envelope.'),
            400: OpenApiResponse(description='Invalid OTP.'),
            401: OpenApiResponse(description='Authentication required.'),
            409: OpenApiResponse(description='Phone already linked to another account.'),
        },
    )
    def post(self, request):
        from user_management.services.phone_otp import PhoneOtpError, bind_phone_otp_to_user

        serializer = PhoneOtpVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            response_data = bind_phone_otp_to_user(
                request.user,
                serializer.validated_data['phone'],
                serializer.validated_data['otp'],
                device_token=serializer.validated_data.get('device_token'),
                platform=serializer.validated_data.get('platform'),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
            )
        except PhoneOtpError as exc:
            status_code = (
                status.HTTP_409_CONFLICT
                if exc.code == 'PHONE_CONFLICT'
                else status.HTTP_400_BAD_REQUEST
            )
            return Response({'detail': exc.message, 'code': exc.code}, status=status_code)
        return Response(response_data)


class GoogleOAuthLoginView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=['Customer Auth'],
        request=GoogleOAuthLoginSerializer,
        description='Verify a Google ID token and create-or-login a customer.',
        responses={
            200: OpenApiResponse(description='Unified auth success envelope.'),
            400: OpenApiResponse(description='Invalid token or configuration.'),
            409: OpenApiResponse(description='Social identity conflict.'),
        },
    )
    def post(self, request):
        from user_management.services.google_oauth import GoogleOAuthError, login_with_google

        serializer = GoogleOAuthLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            response_data = login_with_google(
                serializer.validated_data['id_token'],
                device_token=serializer.validated_data.get('device_token'),
                platform=serializer.validated_data.get('platform'),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
            )
        except GoogleOAuthError as exc:
            status_code = (
                status.HTTP_409_CONFLICT
                if exc.code == 'SOCIAL_CONFLICT'
                else status.HTTP_400_BAD_REQUEST
            )
            return Response({'detail': exc.message, 'code': exc.code}, status=status_code)
        return Response(response_data)


class FacebookOAuthLoginView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=['Customer Auth'],
        request=FacebookOAuthLoginSerializer,
        description='Verify a Facebook access token and create-or-login a customer.',
        responses={
            200: OpenApiResponse(description='Unified auth success envelope.'),
            400: OpenApiResponse(description='Invalid token or configuration.'),
            409: OpenApiResponse(description='Social identity conflict.'),
        },
    )
    def post(self, request):
        from user_management.services.facebook_oauth import FacebookOAuthError, login_with_facebook

        serializer = FacebookOAuthLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            response_data = login_with_facebook(
                serializer.validated_data['access_token'],
                device_token=serializer.validated_data.get('device_token'),
                platform=serializer.validated_data.get('platform'),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
            )
        except FacebookOAuthError as exc:
            status_code = (
                status.HTTP_409_CONFLICT
                if exc.code == 'SOCIAL_CONFLICT'
                else status.HTTP_400_BAD_REQUEST
            )
            return Response({'detail': exc.message, 'code': exc.code}, status=status_code)
        return Response(response_data)


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
