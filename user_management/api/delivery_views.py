from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.services.delivery_address import resync_future_scheduled_deliveries
from user_management.api.delivery_serializers import (
    CustomerDeliveryPlaceSerializer,
    CustomerDeliveryPlaceWriteSerializer,
    CustomerLocationSettingsSerializer,
    DeliveryPreviewItemSerializer,
    DeliveryPreviewQuerySerializer,
    GuestLocationAcceptSerializer,
    GuestLocationOfferQuerySerializer,
    LocationPreferenceRefreshSerializer,
    LocationPreferenceSaveAsPlaceSerializer,
    MealDeliveryDayOverrideReplaceSerializer,
    MealDeliveryDayOverrideSerializer,
    MealDeliveryPreferenceSerializer,
    MealDeliveryPreferenceWriteSerializer,
    SetActivePlaceSerializer,
)
from user_management.api.permissions import HasCustomerProfile, IsCustomerDeliveryPlaceOwner, IsVerifiedAdmin
from user_management.models import CustomerDeliveryPlace
from user_management.services.delivery_place import (
    ADDRESS_LIMIT_REACHED,
    LOCATION_ALREADY_EXISTS,
    DeliveryPlaceError,
    create_delivery_place,
    delete_delivery_place,
    get_place_or_error,
    update_delivery_place,
)
from user_management.services.delivery_preference import (
    DeliveryPreferenceError,
    get_or_create_preference,
    preview_delivery_addresses,
    replace_day_overrides,
    set_meal_delivery_preferences,
)
from user_management.services.location_preference import (
    LocationPreferenceError,
    accept_guest_location_offer,
    clear_location_preference,
    decline_guest_location_offer,
    get_guest_location_offer,
    get_location_preference_payload,
    get_location_settings,
    refresh_detected_location,
    save_detected_as_place,
    serialize_location_preference,
    set_active_from_place,
    update_location_settings,
)


def _error_payload(message, code, errors=None):
    return {
        'success': False,
        'message': message,
        'errors': errors or {},
        'error_code': code,
    }


def _map_place_error(exc: DeliveryPlaceError):
    if exc.code == 'not_found':
        raise NotFound(str(exc)) from exc
    if exc.code in (LOCATION_ALREADY_EXISTS, ADDRESS_LIMIT_REACHED):
        return Response(
            _error_payload(str(exc), exc.code),
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    if exc.code == 'in_use':
        raise ValidationError({'detail': [str(exc)]}) from exc
    raise ValidationError({'detail': [str(exc)]}) from exc


def _map_pref_error(exc: DeliveryPreferenceError | DeliveryPlaceError | LocationPreferenceError):
    code = getattr(exc, 'code', None)
    if code == 'not_found':
        raise NotFound(str(exc)) from exc
    if code == 'already_resolved':
        return Response(
            _error_payload(str(exc), 'GUEST_OFFER_ALREADY_RESOLVED'),
            status=status.HTTP_409_CONFLICT,
        )
    if code in (LOCATION_ALREADY_EXISTS, ADDRESS_LIMIT_REACHED):
        return Response(
            _error_payload(str(exc), code),
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    raise ValidationError({'detail': [str(exc)]}) from exc


def _preference_response(pref, *, warning_code=None, place=None, http_status=status.HTTP_200_OK):
    payload = serialize_location_preference(pref)
    if place is not None:
        payload['place'] = CustomerDeliveryPlaceSerializer(place).data
    if warning_code:
        payload['warning_code'] = warning_code
    return Response(payload, status=http_status)


class CustomerDeliveryPlaceViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [HasCustomerProfile, IsCustomerDeliveryPlaceOwner]
    lookup_field = 'public_id'
    lookup_url_kwarg = 'public_id'
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        return CustomerDeliveryPlace.objects.filter(
            customer_profile=self.request.user.customer_profile
        ).order_by('-created_at')

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return CustomerDeliveryPlaceWriteSerializer
        return CustomerDeliveryPlaceSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            place = create_delivery_place(
                request.user.customer_profile,
                **serializer.validated_data,
            )
        except DeliveryPlaceError as exc:
            mapped = _map_place_error(exc)
            if isinstance(mapped, Response):
                return mapped
            raise
        return Response(
            CustomerDeliveryPlaceSerializer(place).data,
            status=status.HTTP_201_CREATED,
        )

    def partial_update(self, request, *args, **kwargs):
        place = self.get_object()
        serializer = self.get_serializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            place = update_delivery_place(place, **serializer.validated_data)
        except DeliveryPlaceError as exc:
            mapped = _map_place_error(exc)
            if isinstance(mapped, Response):
                return mapped
            raise
        return Response(CustomerDeliveryPlaceSerializer(place).data)

    def destroy(self, request, *args, **kwargs):
        place = self.get_object()
        try:
            delete_delivery_place(place)
        except DeliveryPlaceError as exc:
            mapped = _map_place_error(exc)
            if isinstance(mapped, Response):
                return mapped
            raise
        return Response(status=status.HTTP_204_NO_CONTENT)


class MealDeliveryPreferenceView(APIView):
    permission_classes = [HasCustomerProfile]

    def get(self, request):
        pref = get_or_create_preference(request.user.customer_profile)
        return Response(MealDeliveryPreferenceSerializer(pref).data)

    def put(self, request):
        serializer = MealDeliveryPreferenceWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = request.user.customer_profile
        data = serializer.validated_data

        lunch = None
        dinner = None
        clear_lunch = False
        clear_dinner = False

        if 'lunch_place_id' in data:
            if data['lunch_place_id'] is None:
                clear_lunch = True
            else:
                try:
                    lunch = get_place_or_error(profile, data['lunch_place_id'])
                except DeliveryPlaceError as exc:
                    mapped = _map_place_error(exc)
                    if isinstance(mapped, Response):
                        return mapped
                    raise

        if 'dinner_place_id' in data:
            if data['dinner_place_id'] is None:
                clear_dinner = True
            else:
                try:
                    dinner = get_place_or_error(profile, data['dinner_place_id'])
                except DeliveryPlaceError as exc:
                    mapped = _map_place_error(exc)
                    if isinstance(mapped, Response):
                        return mapped
                    raise

        try:
            pref = set_meal_delivery_preferences(
                profile,
                lunch_place=lunch,
                dinner_place=dinner,
                clear_lunch=clear_lunch,
                clear_dinner=clear_dinner,
            )
        except DeliveryPlaceError as exc:
            mapped = _map_pref_error(exc)
            if isinstance(mapped, Response):
                return mapped
            raise

        resync_future_scheduled_deliveries(profile)
        return Response(MealDeliveryPreferenceSerializer(pref).data)


class MealDeliveryDayOverrideView(APIView):
    permission_classes = [HasCustomerProfile]

    def get(self, request):
        profile = request.user.customer_profile
        rows = profile.meal_delivery_day_overrides.select_related('place').order_by(
            'weekday', 'meal_period'
        )
        return Response(MealDeliveryDayOverrideSerializer(rows, many=True).data)

    def put(self, request):
        serializer = MealDeliveryDayOverrideReplaceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = request.user.customer_profile
        items = []
        for raw in serializer.validated_data['overrides']:
            try:
                place = get_place_or_error(profile, raw['place_id'])
            except DeliveryPlaceError as exc:
                mapped = _map_place_error(exc)
                if isinstance(mapped, Response):
                    return mapped
                raise
            items.append(
                {
                    'meal_period': raw['meal_period'],
                    'weekday': raw['weekday'],
                    'place': place,
                }
            )
        try:
            rows = replace_day_overrides(profile, items)
        except (DeliveryPreferenceError, DeliveryPlaceError) as exc:
            mapped = _map_pref_error(exc)
            if isinstance(mapped, Response):
                return mapped
            raise

        resync_future_scheduled_deliveries(profile)
        return Response(MealDeliveryDayOverrideSerializer(rows, many=True).data)


class MealDeliveryPreferencePreviewView(APIView):
    permission_classes = [HasCustomerProfile]

    def get(self, request):
        query = DeliveryPreviewQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        start = query.validated_data['from']
        end = query.validated_data['to']
        try:
            rows = preview_delivery_addresses(request.user.customer_profile, start, end)
        except DeliveryPreferenceError as exc:
            mapped = _map_pref_error(exc)
            if isinstance(mapped, Response):
                return mapped
            raise

        payload = []
        for row in rows:
            place = row['place']
            payload.append(
                {
                    'service_date': row['service_date'],
                    'meal_period': row['meal_period'],
                    'place_id': place.public_id if place else None,
                    'label': place.label if place else '',
                    'full_address': place.full_address if place else '',
                    'area': place.area if place else '',
                    'city': place.city if place else '',
                }
            )
        return Response(DeliveryPreviewItemSerializer(payload, many=True).data)


class CustomerLocationPreferenceView(APIView):
    permission_classes = [HasCustomerProfile]

    @extend_schema(
        tags=['Customer Location'],
        summary='Get saved vs last-detected location preference',
        responses={200: OpenApiResponse(description='Preference payload')},
    )
    def get(self, request):
        return Response(get_location_preference_payload(request.user.customer_profile))

    @extend_schema(
        tags=['Customer Location'],
        summary='Clear active saved location preference (places retained)',
        responses={200: OpenApiResponse(description='Cleared preference')},
    )
    def delete(self, request):
        pref = clear_location_preference(request.user.customer_profile)
        return _preference_response(pref)


class CustomerLocationPreferenceRefreshView(APIView):
    permission_classes = [HasCustomerProfile]

    @extend_schema(
        tags=['Customer Location'],
        summary='Refresh last-detected GPS without saving a delivery place',
        request=LocationPreferenceRefreshSerializer,
        responses={200: OpenApiResponse(description='Updated preference')},
        examples=[
            OpenApiExample(
                'Refresh GPS',
                value={
                    'latitude': '22.357825',
                    'longitude': '91.846267',
                    'accuracy': '12.5',
                    'location_name': 'Chawkbazar, Chattogram',
                    'source': 'gps',
                },
                request_only=True,
            ),
        ],
    )
    def patch(self, request):
        serializer = LocationPreferenceRefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            pref, warning = refresh_detected_location(
                request.user.customer_profile,
                latitude=data['latitude'],
                longitude=data['longitude'],
                accuracy=data.get('accuracy'),
                location_name=data.get('location_name'),
                source=data.get('source') or 'gps',
            )
        except Exception as exc:
            from user_management.services.location_service import LocationServiceError

            if isinstance(exc, LocationServiceError):
                raise ValidationError({'detail': [str(exc)]}) from exc
            raise
        return _preference_response(pref, warning_code=warning)


class CustomerLocationPreferenceSaveAsPlaceView(APIView):
    permission_classes = [HasCustomerProfile]

    @extend_schema(
        tags=['Customer Location'],
        summary='Save location as a delivery place (does not auto-change lunch/dinner)',
        request=LocationPreferenceSaveAsPlaceSerializer,
        responses={
            201: OpenApiResponse(description='Place created'),
            422: OpenApiResponse(description='Duplicate or address limit'),
        },
    )
    def post(self, request):
        serializer = LocationPreferenceSaveAsPlaceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            place, pref, warning = save_detected_as_place(
                request.user.customer_profile,
                **data,
            )
        except (DeliveryPlaceError, LocationPreferenceError) as exc:
            mapped = _map_pref_error(exc)
            if isinstance(mapped, Response):
                return mapped
            raise
        if data.get('set_lunch_default') or data.get('set_dinner_default') or data.get(
            'set_as_default_delivery_place'
        ):
            resync_future_scheduled_deliveries(request.user.customer_profile)
        return _preference_response(
            pref,
            warning_code=warning,
            place=place,
            http_status=status.HTTP_201_CREATED,
        )


class CustomerLocationGuestOfferView(APIView):
    permission_classes = [HasCustomerProfile]

    @extend_schema(
        tags=['Customer Location'],
        summary='Get guest session location offer after login',
        parameters=[],
        responses={200: OpenApiResponse(description='Guest offer or exists=false')},
    )
    def get(self, request):
        query = GuestLocationOfferQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        return Response(
            get_guest_location_offer(
                request.user.customer_profile,
                query.validated_data['guest_session_id'],
            )
        )

    @extend_schema(
        tags=['Customer Location'],
        summary='Accept guest location offer as delivery place (guest_migration source)',
        request=GuestLocationAcceptSerializer,
        responses={
            201: OpenApiResponse(description='Place created'),
            404: OpenApiResponse(description='No guest history'),
            409: OpenApiResponse(description='Offer already resolved'),
            422: OpenApiResponse(description='Duplicate or address limit'),
        },
    )
    def post(self, request):
        serializer = GuestLocationAcceptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            place, pref, warning = accept_guest_location_offer(
                request.user.customer_profile,
                guest_session_id=data['guest_session_id'],
                label=data['label'],
                full_address=data.get('full_address'),
                formatted_address=data.get('formatted_address'),
                set_lunch_default=data.get('set_lunch_default', False),
                set_dinner_default=data.get('set_dinner_default', False),
                set_as_default_delivery_place=data.get('set_as_default_delivery_place', False),
            )
        except (DeliveryPlaceError, LocationPreferenceError) as exc:
            mapped = _map_pref_error(exc)
            if isinstance(mapped, Response):
                return mapped
            raise
        if data.get('set_lunch_default') or data.get('set_dinner_default') or data.get(
            'set_as_default_delivery_place'
        ):
            resync_future_scheduled_deliveries(request.user.customer_profile)
        return _preference_response(
            pref,
            warning_code=warning,
            place=place,
            http_status=status.HTTP_201_CREATED,
        )


class CustomerLocationGuestOfferDeclineView(APIView):
    permission_classes = [HasCustomerProfile]

    @extend_schema(
        tags=['Customer Location'],
        summary='Decline guest location offer (durable; no delivery place created)',
        request=GuestLocationOfferQuerySerializer,
        responses={200: OpenApiResponse(description='Offer declined / already resolved')},
    )
    def post(self, request):
        serializer = GuestLocationOfferQuerySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            payload = decline_guest_location_offer(
                request.user.customer_profile,
                guest_session_id=serializer.validated_data['guest_session_id'],
            )
        except LocationPreferenceError as exc:
            mapped = _map_pref_error(exc)
            if isinstance(mapped, Response):
                return mapped
            raise
        return Response(payload)


class CustomerLocationSetActivePlaceView(APIView):
    permission_classes = [HasCustomerProfile]

    @extend_schema(
        tags=['Customer Location'],
        summary='Set active saved location from an existing delivery place',
        request=SetActivePlaceSerializer,
    )
    def post(self, request):
        serializer = SetActivePlaceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            pref = set_active_from_place(
                request.user.customer_profile,
                serializer.validated_data['place_id'],
            )
        except DeliveryPlaceError as exc:
            mapped = _map_place_error(exc)
            if isinstance(mapped, Response):
                return mapped
            raise
        return _preference_response(pref)


class CustomerLocationSettingsView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=['Admin Customer Location'],
        summary='Get customer location settings',
        responses={200: CustomerLocationSettingsSerializer},
    )
    def get(self, request):
        return Response(CustomerLocationSettingsSerializer(get_location_settings()).data)

    @extend_schema(
        tags=['Admin Customer Location'],
        summary='Update customer location settings',
        request=CustomerLocationSettingsSerializer,
        responses={200: CustomerLocationSettingsSerializer},
    )
    def patch(self, request):
        settings_obj = get_location_settings()
        serializer = CustomerLocationSettingsSerializer(
            settings_obj, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        updated = update_location_settings(
            duplicate_radius_km=serializer.validated_data.get('duplicate_radius_km'),
            max_active_delivery_places=serializer.validated_data.get(
                'max_active_delivery_places'
            ),
            location_refresh_interval_hours=serializer.validated_data.get(
                'location_refresh_interval_hours'
            ),
        )
        return Response(CustomerLocationSettingsSerializer(updated).data)
