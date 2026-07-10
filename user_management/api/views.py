from django.contrib.auth.models import User
from django.contrib.auth import login as django_login
from django.http import HttpResponse
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import permissions, status
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.views import APIView

from ..services.auth_service import get_login_response, register_customer
from ..services.email_verification import get_user_from_uid, mark_email_verified, send_activation_email, verify_token
from .serializers import CurrentUserSerializer, CustomerLoginSerializer, CustomerRegistrationSerializer, ResendVerificationSerializer


class CustomerRegistrationView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=['Customer Auth'],
        request=CustomerRegistrationSerializer,
        responses={201: OpenApiResponse(response=None, description='Registration successful')},
        examples=[
            OpenApiExample('Success', value={'message': 'Registration successful. Please check your email to verify your account.', 'email': 'customer@example.com'})
        ],
        description='Register a new customer account and send verification email.',
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

    @extend_schema(tags=['Customer Auth'], request=ResendVerificationSerializer, description='Resend the verification email for an unverified account.')
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


class CustomerLoginView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(tags=['Customer Auth'], request=CustomerLoginSerializer, description='Login customer using email and password.')
    def post(self, request):
        serializer = CustomerLoginSerializer(data=request.data)
        if not serializer.is_valid():
            errors = serializer.errors
            if 'non_field_errors' in errors and errors['non_field_errors']:
                detail = errors['non_field_errors'][0]
                return Response({'detail': str(detail)}, status=status.HTTP_400_BAD_REQUEST)
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)
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
