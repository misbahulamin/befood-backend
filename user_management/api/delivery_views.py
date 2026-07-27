from rest_framework import mixins, status, viewsets
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.services.delivery_address import resync_future_scheduled_deliveries
from user_management.api.delivery_serializers import (
    CustomerDeliveryPlaceSerializer,
    CustomerDeliveryPlaceWriteSerializer,
    DeliveryPreviewItemSerializer,
    DeliveryPreviewQuerySerializer,
    MealDeliveryDayOverrideReplaceSerializer,
    MealDeliveryDayOverrideSerializer,
    MealDeliveryPreferenceSerializer,
    MealDeliveryPreferenceWriteSerializer,
)
from user_management.api.permissions import HasCustomerProfile, IsCustomerDeliveryPlaceOwner
from user_management.models import CustomerDeliveryPlace
from user_management.services.delivery_place import (
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


def _map_place_error(exc: DeliveryPlaceError):
    if exc.code == 'not_found':
        raise NotFound(str(exc)) from exc
    if exc.code == 'in_use':
        raise ValidationError({'detail': [str(exc)]}) from exc
    raise ValidationError({'detail': [str(exc)]}) from exc


def _map_pref_error(exc: DeliveryPreferenceError | DeliveryPlaceError):
    if getattr(exc, 'code', None) == 'not_found':
        raise NotFound(str(exc)) from exc
    raise ValidationError({'detail': [str(exc)]}) from exc


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
            _map_place_error(exc)
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
            _map_place_error(exc)
        return Response(CustomerDeliveryPlaceSerializer(place).data)

    def destroy(self, request, *args, **kwargs):
        place = self.get_object()
        try:
            delete_delivery_place(place)
        except DeliveryPlaceError as exc:
            _map_place_error(exc)
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
                    _map_place_error(exc)

        if 'dinner_place_id' in data:
            if data['dinner_place_id'] is None:
                clear_dinner = True
            else:
                try:
                    dinner = get_place_or_error(profile, data['dinner_place_id'])
                except DeliveryPlaceError as exc:
                    _map_place_error(exc)

        try:
            pref = set_meal_delivery_preferences(
                profile,
                lunch_place=lunch,
                dinner_place=dinner,
                clear_lunch=clear_lunch,
                clear_dinner=clear_dinner,
            )
        except DeliveryPlaceError as exc:
            _map_pref_error(exc)

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
                _map_place_error(exc)
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
            _map_pref_error(exc)

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
            _map_pref_error(exc)

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
