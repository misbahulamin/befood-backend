from datetime import date, timedelta

from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from orders.models import CustomerSubscription, Order, OrderDelivery
from orders.services.delivery_address import resync_future_scheduled_deliveries
from orders.services.order_delivery import generate_order_deliveries
from user_management.models import (
    CustomerAddress,
    CustomerDeliveryPlace,
    CustomerLocationSettings,
    CustomerProfile,
    MealDeliveryPreference,
)
from user_management.services.delivery_place import (
    MAX_ACTIVE_DELIVERY_PLACES,
    create_delivery_place,
)
from user_management.services.delivery_preference import (
    resolve_delivery_address,
    set_meal_delivery_preferences,
    replace_day_overrides,
)


class DeliveryAddressAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='delivery_cust',
            email='delivery@example.com',
            password='StrongPassword123',
        )
        self.profile = CustomerProfile.objects.create(
            user=self.user,
            phone='1711111111',
            occupation=CustomerProfile.Occupation.STUDENT,
            is_bachelor=True,
            is_email_verified=True,
        )
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')

        self.other = User.objects.create_user(
            username='other_cust',
            email='other@example.com',
            password='StrongPassword123',
        )
        self.other_profile = CustomerProfile.objects.create(
            user=self.other,
            phone='1722222222',
            occupation=CustomerProfile.Occupation.STUDENT,
            is_bachelor=True,
            is_email_verified=True,
        )

        self.places_url = reverse('user_management:customer-delivery-place-list')
        self.prefs_url = reverse('user_management:customer-delivery-preferences')
        self.overrides_url = reverse('user_management:customer-delivery-day-overrides')
        self.preview_url = reverse('user_management:customer-delivery-preferences-preview')

    def _create_place(self, label='Home', full_address='House 1, Dhaka', **extra):
        payload = {'label': label, 'full_address': full_address, **extra}
        response = self.client.post(self.places_url, payload, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        return response.data

    def test_create_list_place(self):
        data = self._create_place()
        self.assertEqual(data['label'], 'Home')
        listing = self.client.get(self.places_url)
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(len(listing.data), 1)

    def test_unauthenticated_rejected(self):
        self.client.credentials()
        response = self.client.get(self.places_url)
        self.assertEqual(response.status_code, 401)

    def test_missing_full_address_rejected(self):
        response = self.client.post(
            self.places_url,
            {'label': 'Office'},
            format='json',
        )
        self.assertEqual(response.status_code, 400)

    def test_foreign_place_not_found(self):
        other_place = CustomerDeliveryPlace.objects.create(
            customer_profile=self.other_profile,
            label='Secret',
            full_address='Elsewhere',
        )
        url = reverse(
            'user_management:customer-delivery-place-detail',
            kwargs={'public_id': other_place.public_id},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_soft_cap(self):
        settings_obj = CustomerLocationSettings.load()
        settings_obj.max_active_delivery_places = MAX_ACTIVE_DELIVERY_PLACES
        settings_obj.save()
        for i in range(MAX_ACTIVE_DELIVERY_PLACES):
            create_delivery_place(
                self.profile,
                label=f'P{i}',
                full_address=f'Addr {i}',
            )
        response = self.client.post(
            self.places_url,
            {'label': 'Overflow', 'full_address': 'Too many'},
            format='json',
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.data.get('error_code'), 'ADDRESS_LIMIT_REACHED')

    def test_delete_blocked_when_in_use(self):
        home = self._create_place('Home')
        office = self._create_place('Office', 'Office Rd')
        self.client.put(
            self.prefs_url,
            {'lunch_place_id': home['public_id'], 'dinner_place_id': office['public_id']},
            format='json',
        )
        url = reverse(
            'user_management:customer-delivery-place-detail',
            kwargs={'public_id': home['public_id']},
        )
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 400)

    def test_preferences_and_ownership(self):
        home = self._create_place('Home')
        foreign = CustomerDeliveryPlace.objects.create(
            customer_profile=self.other_profile,
            label='Foreign',
            full_address='No',
        )
        bad = self.client.put(
            self.prefs_url,
            {'lunch_place_id': str(foreign.public_id)},
            format='json',
        )
        self.assertEqual(bad.status_code, 404)

        ok = self.client.put(
            self.prefs_url,
            {
                'lunch_place_id': home['public_id'],
                'dinner_place_id': home['public_id'],
            },
            format='json',
        )
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(str(ok.data['lunch_place_id']), home['public_id'])
        self.assertEqual(str(ok.data['dinner_place_id']), home['public_id'])

    def test_day_overrides_replace_set(self):
        home = self._create_place('Home')
        office = self._create_place('Office', 'Office')
        self.client.put(
            self.prefs_url,
            {
                'lunch_place_id': home['public_id'],
                'dinner_place_id': home['public_id'],
            },
            format='json',
        )
        response = self.client.put(
            self.overrides_url,
            {
                'overrides': [
                    {
                        'meal_period': 'lunch',
                        'weekday': 0,
                        'place_id': office['public_id'],
                    },
                    {
                        'meal_period': 'lunch',
                        'weekday': 1,
                        'place_id': office['public_id'],
                    },
                ]
            },
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

    def test_resolution_override_default_weekend(self):
        home = create_delivery_place(self.profile, label='Home', full_address='Home Addr')
        office = create_delivery_place(self.profile, label='Office', full_address='Office Addr')
        set_meal_delivery_preferences(
            self.profile, lunch_place=home, dinner_place=home
        )
        replace_day_overrides(
            self.profile,
            [
                {'meal_period': 'lunch', 'weekday': 0, 'place': office},  # Monday
                {'meal_period': 'lunch', 'weekday': 1, 'place': office},
                {'meal_period': 'lunch', 'weekday': 2, 'place': office},
                {'meal_period': 'lunch', 'weekday': 3, 'place': office},
                {'meal_period': 'lunch', 'weekday': 4, 'place': office},
            ],
        )
        monday = date(2026, 7, 27)  # Monday
        saturday = date(2026, 8, 1)  # Saturday
        self.assertEqual(resolve_delivery_address(self.profile, monday, 'lunch').pk, office.pk)
        self.assertEqual(resolve_delivery_address(self.profile, saturday, 'lunch').pk, home.pk)
        self.assertEqual(resolve_delivery_address(self.profile, monday, 'dinner').pk, home.pk)

    def test_preview_endpoint(self):
        home = self._create_place('Home')
        self.client.put(
            self.prefs_url,
            {'lunch_place_id': home['public_id'], 'dinner_place_id': home['public_id']},
            format='json',
        )
        response = self.client.get(
            self.preview_url,
            {'from': '2026-07-27', 'to': '2026-07-28'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 4)  # 2 days × 2 periods

    def test_order_delivery_snapshot_and_immutability(self):
        from decimal import Decimal

        from django.core.files.uploadedfile import SimpleUploadedFile

        from meals.models import MealCategory

        home = create_delivery_place(self.profile, label='Home', full_address='Home Addr')
        office = create_delivery_place(self.profile, label='Office', full_address='Office Addr')
        set_meal_delivery_preferences(
            self.profile, lunch_place=home, dinner_place=home
        )

        thumb = SimpleUploadedFile('t.jpg', b'fake', content_type='image/jpeg')
        meal = MealCategory.objects.create(
            meal_name='Test Package',
            total_price=Decimal('350.00'),
            meal_thumbnail=thumb,
            meal_type=MealCategory.MealType.DAILY,
            meal_period=MealCategory.MealPeriod.LUNCH,
            is_active=True,
        )

        order = Order.objects.create(
            customer=self.profile,
            meal=meal,
            meal_name_snapshot=meal.meal_name,
            meal_type_snapshot=meal.meal_type,
            meal_period_snapshot='lunch',
            total_price_snapshot='350.00',
            per_meal_price_snapshot='350.00',
            order_start_date=date(2026, 7, 27),
            order_end_date=date(2026, 7, 27),
            service_days_count=1,
            order_month='2026-07',
        )
        deliveries = generate_order_deliveries(order)
        self.assertEqual(len(deliveries), 1)
        delivery = deliveries[0]
        self.assertEqual(delivery.delivery_label_snapshot, 'Home')
        self.assertEqual(delivery.delivery_full_address_snapshot, 'Home Addr')

        delivery.status = OrderDelivery.DeliveryStatus.DELIVERED
        delivery.save(update_fields=['status', 'updated_at'])

        set_meal_delivery_preferences(
            self.profile, lunch_place=office, dinner_place=office
        )
        resync_future_scheduled_deliveries(self.profile, reference_date=date(2026, 7, 1))
        delivery.refresh_from_db()
        self.assertEqual(delivery.delivery_label_snapshot, 'Home')

    def test_future_scheduled_resync(self):
        from decimal import Decimal

        from django.core.files.uploadedfile import SimpleUploadedFile

        from meals.models import MealCategory

        home = create_delivery_place(self.profile, label='Home', full_address='Home Addr')
        office = create_delivery_place(self.profile, label='Office', full_address='Office Addr')
        set_meal_delivery_preferences(
            self.profile, lunch_place=home, dinner_place=home
        )

        thumb = SimpleUploadedFile('t2.jpg', b'fake', content_type='image/jpeg')
        meal = MealCategory.objects.create(
            meal_name='Pkg2',
            total_price=Decimal('350.00'),
            meal_thumbnail=thumb,
            meal_type=MealCategory.MealType.DAILY,
            meal_period=MealCategory.MealPeriod.LUNCH,
            is_active=True,
        )
        future = date.today() + timedelta(days=3)
        order = Order.objects.create(
            customer=self.profile,
            meal=meal,
            meal_name_snapshot=meal.meal_name,
            meal_type_snapshot=meal.meal_type,
            meal_period_snapshot='lunch',
            total_price_snapshot='350.00',
            per_meal_price_snapshot='350.00',
            order_start_date=future,
            order_end_date=future,
            service_days_count=1,
            order_month=future.strftime('%Y-%m'),
        )
        delivery = generate_order_deliveries(order)[0]
        self.assertEqual(delivery.delivery_label_snapshot, 'Home')

        set_meal_delivery_preferences(
            self.profile, lunch_place=office, dinner_place=office
        )
        updated = resync_future_scheduled_deliveries(self.profile)
        self.assertGreaterEqual(updated, 1)
        delivery.refresh_from_db()
        self.assertEqual(delivery.delivery_label_snapshot, 'Office')

    def test_subscription_owned_resync_and_preferences_put(self):
        """
        Preference PUT + resync must succeed on Postgres when deliveries have
        subscription set and order null (nullable outer-join + FOR UPDATE).
        """
        from decimal import Decimal

        from django.core.files.uploadedfile import SimpleUploadedFile

        from meals.models import MealCategory

        home = create_delivery_place(self.profile, label='Home', full_address='Home Addr')
        office = create_delivery_place(self.profile, label='Office', full_address='Office Addr')
        set_meal_delivery_preferences(
            self.profile, lunch_place=home, dinner_place=home
        )

        thumb = SimpleUploadedFile('t3.jpg', b'fake', content_type='image/jpeg')
        meal = MealCategory.objects.create(
            meal_name='SubPkg',
            total_price=Decimal('350.00'),
            meal_thumbnail=thumb,
            meal_type=MealCategory.MealType.DAILY,
            meal_period=MealCategory.MealPeriod.LUNCH,
            is_active=True,
        )
        future = date.today() + timedelta(days=5)
        subscription = CustomerSubscription.objects.create(
            customer=self.profile,
            meal=meal,
            meal_name_snapshot=meal.meal_name,
            meal_period_snapshot='lunch',
            status=CustomerSubscription.Status.ACTIVE,
            started_on=date.today(),
        )
        delivery = OrderDelivery.objects.create(
            order=None,
            subscription=subscription,
            service_date=future,
            meal_period=OrderDelivery.MealPeriod.LUNCH,
            status=OrderDelivery.DeliveryStatus.SCHEDULED,
            delivery_label_snapshot='Home',
            delivery_full_address_snapshot='Home Addr',
        )

        response = self.client.put(
            self.prefs_url,
            {
                'lunch_place_id': str(office.public_id),
                'dinner_place_id': str(office.public_id),
            },
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(str(response.data['lunch_place_id']), str(office.public_id))

        delivery.refresh_from_db()
        self.assertEqual(delivery.delivery_label_snapshot, 'Office')
        self.assertEqual(delivery.delivery_full_address_snapshot, 'Office Addr')

        # Day-override PUT also triggers resync; must not 500 on the same join shape.
        override_response = self.client.put(
            self.overrides_url,
            {
                'overrides': [
                    {
                        'meal_period': 'lunch',
                        'weekday': future.weekday(),
                        'place_id': str(home.public_id),
                    }
                ]
            },
            format='json',
        )
        self.assertEqual(override_response.status_code, 200, override_response.data)
        delivery.refresh_from_db()
        self.assertEqual(delivery.delivery_label_snapshot, 'Home')

    def test_backfill_from_present_default(self):
        CustomerAddress.objects.create(
            customer_profile=self.profile,
            address_type=CustomerAddress.AddressType.PRESENT,
            full_address='Present Home, Banani',
            city='Dhaka',
            area='Banani',
            is_default_delivery=True,
        )
        place = resolve_delivery_address(self.profile, date(2026, 7, 27), 'lunch')
        self.assertIsNotNone(place)
        self.assertIn('Present Home', place.full_address)
        pref = MealDeliveryPreference.objects.get(customer_profile=self.profile)
        self.assertEqual(pref.lunch_place_id, place.pk)
        self.assertEqual(pref.dinner_place_id, place.pk)
