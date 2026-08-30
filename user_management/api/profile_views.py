from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import CustomerAddress
from ..services.customer_address import handle_default_on_delete, set_default_delivery_address
from ..services.profile_completion import update_profile_completion
from .permissions import HasCustomerProfile, IsCustomerAddressOwner
from .profile_serializers import (
    CustomerAddressCreateUpdateSerializer,
    CustomerAddressSerializer,
    CustomerExtendedProfileSerializer,
    CustomerExtendedProfileUpdateSerializer,
    CustomerProfileCompletionSerializer,
    CustomerProfileImageUploadSerializer,
)


class CustomerProfileView(APIView):
    permission_classes = [HasCustomerProfile]

    def _get_profile(self, request):
        return request.user.customer_profile

    @extend_schema(
        tags=['Customer Profile'],
        responses={200: CustomerExtendedProfileSerializer},
        description='Get extended customer profile with addresses and completion status.',
    )
    def get(self, request):
        profile = self._get_profile(request)
        update_profile_completion(profile)
        profile.refresh_from_db()
        data = CustomerExtendedProfileSerializer(profile, context={'request': request}).data
        data['profile_completion_percentage'] = profile.profile_completion_percentage
        data['profile_completed'] = profile.profile_completed
        return Response(data)

    @extend_schema(
        tags=['Customer Profile'],
        request=CustomerExtendedProfileUpdateSerializer,
        responses={200: CustomerExtendedProfileSerializer},
        examples=[
            OpenApiExample(
                'Update names only',
                value={'first_name': 'John', 'last_name': 'Doe'},
                request_only=True,
            ),
            OpenApiExample(
                'Update phone only',
                value={'phone': '1712345678'},
                request_only=True,
            ),
            OpenApiExample(
                'Update demographics',
                value={'gender': 'male', 'is_bachelor': True, 'occupation': 'student'},
                request_only=True,
            ),
            OpenApiExample(
                'Update extended profile',
                value={
                    'birth_date': '2000-05-15',
                    'gender': 'male',
                    'height_cm': '170.50',
                    'weight_kg': '65.50',
                    'emergency_contact_name': 'Rahim Uddin',
                    'emergency_contact_phone': '1812345678',
                    'organization_name': 'Dhaka University',
                    'academic_year_or_position': '3rd Year',
                    'has_allergy': True,
                    'allergy_details': 'Shrimp and peanuts',
                    'restricted_foods': 'Beef, too spicy food',
                    'preferred_food_type': 'regular',
                    'spice_level': 'medium',
                    'religious': 'islam',
                    'delivery_instruction': 'Call before delivery',
                    'preferred_delivery_time': '13:30',
                },
                request_only=True,
            ),
        ],
        description=(
            'Partially update customer onboarding and extended profile fields. '
            'Submitted fields are validated and persisted immediately.'
        ),
    )
    def patch(self, request):
        profile = self._get_profile(request)
        serializer = CustomerExtendedProfileUpdateSerializer(
            profile,
            data=request.data,
            partial=True,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        profile.refresh_from_db()
        data = CustomerExtendedProfileSerializer(profile, context={'request': request}).data
        data['profile_completion_percentage'] = profile.profile_completion_percentage
        data['profile_completed'] = profile.profile_completed
        return Response(data)


class CustomerProfileImageUploadView(APIView):
    permission_classes = [HasCustomerProfile]

    @extend_schema(
        tags=['Customer Profile'],
        request=CustomerProfileImageUploadSerializer,
        responses={
            200: OpenApiResponse(description='Profile picture uploaded'),
        },
        description=(
            'Upload a customer profile picture (multipart field `image`). '
            'Stored via default media storage (S3 when USE_S3_MEDIA=true).'
        ),
    )
    def post(self, request):
        profile = request.user.customer_profile
        serializer = CustomerProfileImageUploadSerializer(
            data=request.data,
            context={'request': request, 'customer_profile': profile},
        )
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        url = result['profile_image_url']
        if url and request and not str(url).startswith(('http://', 'https://')):
            url = request.build_absolute_uri(url)
            result = {**result, 'profile_image_url': url}
        return Response(result, status=status.HTTP_200_OK)


class CustomerAddressViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [HasCustomerProfile, IsCustomerAddressOwner]
    lookup_field = 'public_id'
    lookup_url_kwarg = 'public_id'
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        return CustomerAddress.objects.filter(
            customer_profile=self.request.user.customer_profile
        ).order_by('-created_at')

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return CustomerAddressCreateUpdateSerializer
        return CustomerAddressSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['customer_profile'] = self.request.user.customer_profile
        return context

    @extend_schema(tags=['Customer Profile'])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        tags=['Customer Profile'],
        request=CustomerAddressCreateUpdateSerializer,
        responses={201: CustomerAddressSerializer},
        examples=[
            OpenApiExample(
                'Create present address',
                value={
                    'address_type': 'present',
                    'full_address': 'House 12, Road 5, Mirpur',
                    'city': 'Dhaka',
                    'area': 'Mirpur',
                    'building_name': 'Green Tower',
                    'floor': '5th Floor',
                    'flat_number': 'A-5',
                    'landmark': 'Beside Mirpur Mosque',
                    'latitude': '23.810331',
                    'longitude': '90.412521',
                    'is_default_delivery': True,
                },
                request_only=True,
            )
        ],
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(tags=['Customer Profile'])
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(tags=['Customer Profile'], request=CustomerAddressCreateUpdateSerializer)
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(tags=['Customer Profile'], responses={204: OpenApiResponse(description='Deleted')})
    def destroy(self, request, *args, **kwargs):
        address = self.get_object()
        customer_profile = address.customer_profile
        was_default = address.is_default_delivery
        address.delete()
        if was_default:
            handle_default_on_delete(customer_profile, was_default=True)
        else:
            update_profile_completion(customer_profile)
        return Response(status=status.HTTP_204_NO_CONTENT)


class SetDefaultDeliveryAddressView(APIView):
    permission_classes = [HasCustomerProfile]

    @extend_schema(
        tags=['Customer Profile'],
        responses={200: CustomerAddressSerializer},
        description='Set a present address as the default delivery address.',
    )
    def post(self, request, public_id):
        profile = request.user.customer_profile
        try:
            address = CustomerAddress.objects.get(public_id=public_id, customer_profile=profile)
        except CustomerAddress.DoesNotExist:
            raise NotFound('Address not found.')
        try:
            address = set_default_delivery_address(profile, address)
        except ValueError as exc:
            raise ValidationError({'detail': str(exc)})
        return Response(CustomerAddressSerializer(address).data)
