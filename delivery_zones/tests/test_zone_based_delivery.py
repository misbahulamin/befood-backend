from datetime import date
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from PIL import Image
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from delivery_zones.models import DeliveryLocation, DeliveryZone
from delivery_zones.services.assignment import (
    assign_customer_location,
    clear_customer_location,
    derived_zone,
)
from delivery_zones.services.errors import DeliveryZoneError
from delivery_zones.services.locations import (
    create_location,
    delete_location_if_empty,
    move_location_to_zone,
    update_location,
)
from delivery_zones.services.ops import build_ops_summary
from delivery_zones.services.zones import (
    assign_delivery_man,
    create_zone,
    delete_zone_if_empty,
)
from meals.models import (
    Ingredient,
    MealCategory,
    MealCycle,
    MealCyclePlan,
    MonthlyMenuSchedule,
    MonthlyMenuSlot,
    MonthlyMenuSlotItem,
)
from orders.models import CustomerSubscription, OrderDelivery
from user_management.models import AdminProfile, CustomerProfile, RiderProfile


def make_test_image(name='meal.jpg', size=(100, 100), color='red'):
    buffer = BytesIO()
    image = Image.new('RGB', size, color)
    image.save(buffer, format='JPEG')
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type='image/jpeg')


class DeliveryZoneServiceTests(TestCase):
    def setUp(self):
        Group.objects.get_or_create(name='DELIVERY_MAN')
        rider_user = User.objects.create_user(
            username='rider1',
            email='rider1@example.com',
            password='StrongPassword123',
            first_name='Rahim',
            is_active=True,
        )
        self.rider = RiderProfile.objects.create(
            user=rider_user,
            phone='1711000001',
            approval_status=RiderProfile.ApprovalStatus.APPROVED,
            is_verified=True,
            is_email_verified=True,
            verified_at=timezone.now(),
        )
        pending_user = User.objects.create_user(
            username='rider_pending',
            email='pending@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.pending_rider = RiderProfile.objects.create(
            user=pending_user,
            phone='1711000002',
            approval_status=RiderProfile.ApprovalStatus.PENDING,
            is_verified=False,
            is_email_verified=True,
        )

    def test_create_zone_and_priority_uniqueness(self):
        z1 = create_zone(name='Zone 1', code='zone-1', priority=1)
        self.assertEqual(z1.priority, 1)
        with self.assertRaises(DeliveryZoneError) as ctx:
            create_zone(name='Zone X', code='zone-x', priority=1)
        self.assertEqual(ctx.exception.code, 'PRIORITY_CONFLICT')

    def test_assign_rider_uniqueness_and_approval(self):
        z1 = create_zone(name='Zone 1', code='zone-1', priority=1)
        z2 = create_zone(name='Zone 2', code='zone-2', priority=2)
        assign_delivery_man(z1, delivery_man_public_id=self.rider.public_id)
        z1.refresh_from_db()
        self.assertEqual(z1.assigned_delivery_man_id, self.rider.pk)

        with self.assertRaises(DeliveryZoneError) as ctx:
            assign_delivery_man(z2, delivery_man_public_id=self.rider.public_id)
        self.assertEqual(ctx.exception.code, 'DELIVERY_MAN_ALREADY_ASSIGNED')

        with self.assertRaises(DeliveryZoneError) as ctx2:
            assign_delivery_man(z2, delivery_man_public_id=self.pending_rider.public_id)
        self.assertEqual(ctx2.exception.code, 'DELIVERY_MAN_NOT_APPROVED')

    def test_delete_zone_with_locations_blocked(self):
        zone = create_zone(name='Zone 1', code='zone-1', priority=1)
        create_location(name='Chawkbazar', zone_public_id=zone.public_id, priority=1)
        with self.assertRaises(DeliveryZoneError) as ctx:
            delete_zone_if_empty(zone)
        self.assertEqual(ctx.exception.code, 'ZONE_HAS_LOCATIONS')


class DeliveryLocationCascadeTests(TestCase):
    def setUp(self):
        customer_group, _ = Group.objects.get_or_create(name='CUSTOMER')
        user = User.objects.create_user(
            username='cust1',
            email='cust1@example.com',
            password='StrongPassword123',
            first_name='Karim',
            is_active=True,
        )
        user.groups.add(customer_group)
        self.customer = CustomerProfile.objects.create(
            user=user,
            phone='1712000001',
            is_email_verified=True,
        )
        self.zone1 = create_zone(name='Zone 1', code='zone-1', priority=1)
        self.zone2 = create_zone(name='Zone 2', code='zone-2', priority=2)
        self.location = create_location(
            name='Chawkbazar',
            zone_public_id=self.zone1.public_id,
            priority=1,
        )
        assign_customer_location(self.customer, location_public_id=self.location.public_id)

    def test_cascade_on_location_move(self):
        self.assertEqual(derived_zone(self.customer).pk, self.zone1.pk)
        move_location_to_zone(self.location, zone_public_id=self.zone2.public_id)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.delivery_location_id, self.location.pk)
        self.assertEqual(derived_zone(self.customer).pk, self.zone2.pk)

    def test_delete_location_with_customers_blocked(self):
        with self.assertRaises(DeliveryZoneError) as ctx:
            delete_location_if_empty(self.location)
        self.assertEqual(ctx.exception.code, 'LOCATION_HAS_CUSTOMERS')

    def test_inactive_location_assign_rejected(self):
        update_location(self.location, status=DeliveryLocation.Status.INACTIVE)
        clear_customer_location(self.customer)
        with self.assertRaises(DeliveryZoneError) as ctx:
            assign_customer_location(
                self.customer, location_public_id=self.location.public_id
            )
        self.assertEqual(ctx.exception.code, 'LOCATION_INACTIVE')


class DeliveryZoneAPITests(APITestCase):
    def setUp(self):
        admin_group, _ = Group.objects.get_or_create(name='ADMIN')
        self.admin_user = User.objects.create_user(
            username='dz_admin',
            email='dz_admin@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        self.admin_user.groups.add(admin_group)
        AdminProfile.objects.create(user=self.admin_user, is_verified=True)
        self.admin_token = Token.objects.create(user=self.admin_user)

        customer_group, _ = Group.objects.get_or_create(name='CUSTOMER')
        self.customer_user = User.objects.create_user(
            username='dz_cust',
            email='dz_cust@example.com',
            password='StrongPassword123',
            first_name='Rahim',
            is_active=True,
        )
        self.customer_user.groups.add(customer_group)
        self.customer = CustomerProfile.objects.create(
            user=self.customer_user,
            phone='1713000001',
            is_email_verified=True,
        )
        self.customer_token = Token.objects.create(user=self.customer_user)

        Group.objects.get_or_create(name='DELIVERY_MAN')
        rider_user = User.objects.create_user(
            username='dz_rider',
            email='dz_rider@example.com',
            password='StrongPassword123',
            first_name='Rider',
            is_active=True,
        )
        rider_user.groups.add(Group.objects.get(name='DELIVERY_MAN'))
        self.rider = RiderProfile.objects.create(
            user=rider_user,
            phone='1713000002',
            approval_status=RiderProfile.ApprovalStatus.APPROVED,
            is_verified=True,
            is_email_verified=True,
            verified_at=timezone.now(),
        )
        self.rider_token = Token.objects.create(user=rider_user)

        self.plan = MealCategory.objects.create(
            meal_name='Student Package',
            total_price=Decimal('2737.00'),
            meal_thumbnail=make_test_image('dz_plan.jpg'),
            meal_type=MealCategory.MealType.MONTHLY,
            meal_period=MealCategory.MealPeriod.BOTH,
            is_active=True,
            is_subscribable=True,
        )
        self.service_date = date(2026, 9, 18)

    def _auth_admin(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token.key}')

    def _auth_rider(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.rider_token.key}')

    def _auth_customer(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.customer_token.key}')

    def test_admin_zone_location_crud_and_permissions(self):
        resp = self.client.post(
            '/api/v1/web/delivery-zones/',
            {'name': 'Zone 1', 'code': 'zone-1', 'priority': 1},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

        self._auth_admin()
        resp = self.client.post(
            '/api/v1/web/delivery-zones/',
            {'name': 'Zone 1', 'code': 'zone-1', 'priority': 1},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        zone_id = resp.data['public_id']

        resp = self.client.post(
            '/api/v1/web/delivery-locations/',
            {
                'name': 'Chawkbazar',
                'zone_public_id': zone_id,
                'priority': 1,
            },
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        location_id = resp.data['public_id']

        resp = self.client.patch(
            f'/api/v1/web/delivery-zones/{zone_id}/assign-delivery-man/',
            {'delivery_man_public_id': str(self.rider.public_id)},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(
            resp.data['assigned_delivery_man']['public_id'], str(self.rider.public_id)
        )

        resp = self.client.patch(
            f'/api/v1/web/customers/{self.customer.public_id}/delivery-location/',
            {'delivery_location_public_id': location_id},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['delivery_location']['name'], 'Chawkbazar')
        self.assertEqual(resp.data['delivery_zone']['public_id'], zone_id)

        detail = self.client.get(f'/api/v1/web/customers/{self.customer.public_id}/')
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(detail.data['delivery_location']['public_id'], location_id)
        self.assertEqual(detail.data['delivery_zone']['public_id'], zone_id)

        listed = self.client.get(
            '/api/v1/web/customers/',
            {'zone_public_id': zone_id},
        )
        self.assertEqual(listed.status_code, status.HTTP_200_OK)
        ids = [row['public_id'] for row in listed.data['results']]
        self.assertIn(str(self.customer.public_id), ids)

        locations_listed = self.client.get(
            '/api/v1/web/delivery-locations/',
            {'zone_public_id': zone_id},
        )
        self.assertEqual(locations_listed.status_code, status.HTTP_200_OK)
        location_row = next(
            row
            for row in locations_listed.data['results']
            if row['public_id'] == location_id
        )
        self.assertEqual(location_row['customer_count'], 1)

    def test_inactive_location_assign_api(self):
        self._auth_admin()
        zone = create_zone(name='Zone 1', code='zone-1', priority=1)
        location = create_location(
            name='DC Road', zone_public_id=zone.public_id, priority=1
        )
        update_location(location, status=DeliveryLocation.Status.INACTIVE)
        resp = self.client.patch(
            f'/api/v1/web/customers/{self.customer.public_id}/delivery-location/',
            {'delivery_location_public_id': str(location.public_id)},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(resp.data['error_code'], 'LOCATION_INACTIVE')

    def _seed_delivery(self, customer, location, meal_period='lunch'):
        assign_customer_location(customer, location_public_id=location.public_id)
        subscription = CustomerSubscription.objects.filter(
            customer=customer,
            status=CustomerSubscription.Status.ACTIVE,
        ).first()
        if subscription is None:
            subscription = CustomerSubscription.objects.create(
                customer=customer,
                meal=self.plan,
                meal_name_snapshot=self.plan.meal_name,
                meal_period_snapshot='both',
                status=CustomerSubscription.Status.ACTIVE,
                started_on=self.service_date,
            )
        return OrderDelivery.objects.create(
            subscription=subscription,
            service_date=self.service_date,
            meal_period=meal_period,
            status=OrderDelivery.DeliveryStatus.SCHEDULED,
            delivery_label_snapshot='Home',
            delivery_full_address_snapshot='House 1',
            delivery_area_snapshot=location.name,
            delivery_city_snapshot='Chattogram',
        )

    def test_ops_summary_and_board(self):
        self._auth_admin()
        zone1 = create_zone(name='Zone 1', code='zone-1', priority=1)
        zone2 = create_zone(name='Zone 2', code='zone-2', priority=2)
        loc1 = create_location(
            name='Chawkbazar', zone_public_id=zone1.public_id, priority=1
        )
        loc2 = create_location(
            name='DC Road', zone_public_id=zone1.public_id, priority=2
        )
        assign_delivery_man(zone1, delivery_man_public_id=self.rider.public_id)

        self._seed_delivery(self.customer, loc1, 'lunch')
        other_user = User.objects.create_user(
            username='dz_cust2',
            email='dz_cust2@example.com',
            password='StrongPassword123',
            first_name='Abul',
            is_active=True,
        )
        other = CustomerProfile.objects.create(
            user=other_user,
            phone='1713000003',
            is_email_verified=True,
        )
        self._seed_delivery(other, loc2, 'lunch')

        unassigned_user = User.objects.create_user(
            username='dz_cust3',
            email='dz_cust3@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        unassigned = CustomerProfile.objects.create(
            user=unassigned_user,
            phone='1713000004',
            is_email_verified=True,
        )
        sub = CustomerSubscription.objects.create(
            customer=unassigned,
            meal=self.plan,
            meal_name_snapshot=self.plan.meal_name,
            meal_period_snapshot='both',
            status=CustomerSubscription.Status.ACTIVE,
            started_on=self.service_date,
        )
        OrderDelivery.objects.create(
            subscription=sub,
            service_date=self.service_date,
            meal_period='lunch',
            status=OrderDelivery.DeliveryStatus.SCHEDULED,
        )

        summary = build_ops_summary(
            service_date=self.service_date, meal_period='lunch'
        )
        self.assertEqual(summary['unassigned_location_count'], 1)
        zone_payload = next(z for z in summary['zones'] if z['code'] == 'zone-1')
        self.assertEqual(zone_payload['counts']['scheduled'], 2)
        self.assertEqual(len(zone_payload['locations']), 2)

        resp = self.client.get(
            '/api/v1/web/delivery-zones/ops/summary/',
            {
                'service_date': self.service_date.isoformat(),
                'meal_period': 'lunch',
            },
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['unassigned_location_count'], 1)

        # Today-board zone filter
        board = self.client.get(
            '/api/v1/web/orders/today-board/',
            {
                'service_date': self.service_date.isoformat(),
                'meal_period': 'lunch',
                'zone_public_id': str(zone1.public_id),
            },
        )
        self.assertEqual(board.status_code, status.HTTP_200_OK)
        self.assertEqual(len(board.data), 2)

        legacy = self.client.get(
            '/api/v1/web/orders/today-board/',
            {
                'service_date': self.service_date.isoformat(),
                'meal_period': 'lunch',
            },
        )
        self.assertEqual(legacy.status_code, status.HTTP_200_OK)
        self.assertEqual(len(legacy.data), 3)

        # Deliveryman board (active meal only; client date/period ignored)
        self._auth_rider()
        with patch(
            'delivery_zones.services.board.get_current_delivery_period',
            return_value=(self.service_date, OrderDelivery.MealPeriod.LUNCH),
        ):
            rider_board = self.client.get(
                '/user_management/deliveryman/deliveries/today-board/',
                {
                    'service_date': self.service_date.isoformat(),
                    'meal_period': 'dinner',
                },
            )
        self.assertEqual(rider_board.status_code, status.HTTP_200_OK)
        self.assertEqual(rider_board.data['active_meal_period'], 'lunch')
        self.assertEqual(rider_board.data['total_count'], 2)
        self.assertNotIn('dinner', rider_board.data['periods'])
        self.assertEqual(rider_board.data['periods']['lunch']['total_count'], 2)
        locations = rider_board.data['periods']['lunch']['locations']
        self.assertEqual(locations[0]['location_name'], 'Chawkbazar')
        self.assertEqual(locations[1]['location_name'], 'DC Road')
        customer_row = locations[0]['customers'][0]
        self.assertEqual(customer_row['customer_phone'], '1713000001')
        self.assertNotIn('wallet_balance', customer_row)
        self.assertEqual(customer_row['meal_name'], 'Student Package')
        self.assertEqual(customer_row['menu_items_label'], '')

        # Customer denied
        self._auth_customer()
        denied = self.client.get(
            '/user_management/deliveryman/deliveries/today-board/',
        )
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)

        # No zone → empty
        DeliveryZone.objects.filter(pk=zone1.pk).update(assigned_delivery_man=None)
        self._auth_rider()
        with patch(
            'delivery_zones.services.board.get_current_delivery_period',
            return_value=(self.service_date, OrderDelivery.MealPeriod.LUNCH),
        ):
            empty = self.client.get(
                '/user_management/deliveryman/deliveries/today-board/',
            )
        self.assertEqual(empty.status_code, status.HTTP_200_OK)
        self.assertIsNone(empty.data['zone'])
        self.assertEqual(empty.data['periods'], {})
        self.assertEqual(empty.data['total_count'], 0)

        # zone2 unused to silence lint
        self.assertTrue(DeliveryZone.objects.filter(pk=zone2.pk).exists())

    def test_deliveryman_board_pre_lunch_empty_and_dinner_only(self):
        self._auth_admin()
        zone1 = create_zone(name='Zone 1', code='zone-1', priority=1)
        loc1 = create_location(
            name='Chawkbazar', zone_public_id=zone1.public_id, priority=1
        )
        assign_delivery_man(zone1, delivery_man_public_id=self.rider.public_id)
        self._seed_delivery(self.customer, loc1, 'lunch')
        self._seed_delivery(self.customer, loc1, 'dinner')

        self._auth_rider()
        with patch(
            'delivery_zones.services.board.get_current_delivery_period',
            return_value=(self.service_date, None),
        ):
            empty = self.client.get('/user_management/deliveryman/deliveries/today-board/')
        self.assertEqual(empty.status_code, status.HTTP_200_OK)
        self.assertIsNone(empty.data['active_meal_period'])
        self.assertEqual(empty.data['periods'], {})
        self.assertIn('No active meal', empty.data.get('message', ''))

        with patch(
            'delivery_zones.services.board.get_current_delivery_period',
            return_value=(self.service_date, OrderDelivery.MealPeriod.DINNER),
        ):
            dinner_board = self.client.get(
                '/user_management/deliveryman/deliveries/today-board/'
            )
        self.assertEqual(dinner_board.status_code, status.HTTP_200_OK)
        self.assertEqual(dinner_board.data['active_meal_period'], 'dinner')
        self.assertEqual(dinner_board.data['total_count'], 1)
        self.assertIn('dinner', dinner_board.data['periods'])
        self.assertNotIn('lunch', dinner_board.data['periods'])

    def _seed_published_lunch_menu(self, *ingredient_names: str):
        ingredients = []
        for name in ingredient_names:
            ingredients.append(
                Ingredient.objects.create(
                    name=name,
                    price_per_kg=Decimal('100.00'),
                    customers_per_kg=Decimal('5.00'),
                    is_active=True,
                )
            )
        cycle = MealCycle.objects.create(
            year=self.service_date.year, month=self.service_date.month
        )
        plan = MealCyclePlan.objects.create(
            cycle=cycle,
            meal_category=self.plan,
            status=MealCyclePlan.Status.FINALIZED,
        )
        schedule = MonthlyMenuSchedule.objects.create(
            plan=plan,
            status=MonthlyMenuSchedule.Status.PUBLISHED,
            published_at=timezone.now(),
        )
        slot = MonthlyMenuSlot.objects.create(
            schedule=schedule,
            service_date=self.service_date,
            meal_period=MonthlyMenuSlot.MealPeriod.LUNCH,
        )
        for ingredient in ingredients:
            MonthlyMenuSlotItem.objects.create(slot=slot, ingredient=ingredient)
        return slot

    def test_deliveryman_board_menu_label_and_no_wallet(self):
        self._auth_admin()
        zone1 = create_zone(name='Zone 1', code='zone-1', priority=1)
        loc1 = create_location(
            name='Chawkbazar', zone_public_id=zone1.public_id, priority=1
        )
        assign_delivery_man(zone1, delivery_man_public_id=self.rider.public_id)
        self._seed_delivery(self.customer, loc1, 'lunch')
        self._seed_published_lunch_menu('vat', 'dhal', 'vegetable', 'chicken')

        self._auth_rider()
        with patch(
            'delivery_zones.services.board.get_current_delivery_period',
            return_value=(self.service_date, OrderDelivery.MealPeriod.LUNCH),
        ):
            board = self.client.get(
                '/user_management/deliveryman/deliveries/today-board/'
            )
        self.assertEqual(board.status_code, status.HTTP_200_OK)
        row = board.data['periods']['lunch']['locations'][0]['customers'][0]
        self.assertNotIn('wallet_balance', row)
        self.assertEqual(row['meal_name'], 'Student Package')
        self.assertEqual(
            row['menu_items_label'],
            'chicken + dhal + vat + vegetable',
        )

    def test_deliveryman_board_omits_low_balance_blocked_customers(self):
        self._auth_admin()
        zone1 = create_zone(name='Zone 1', code='zone-1', priority=1)
        loc1 = create_location(
            name='Chawkbazar', zone_public_id=zone1.public_id, priority=1
        )
        assign_delivery_man(zone1, delivery_man_public_id=self.rider.public_id)

        self._seed_delivery(self.customer, loc1, 'lunch')

        blocked_user = User.objects.create_user(
            username='dz_blocked',
            email='dz_blocked@example.com',
            password='StrongPassword123',
            first_name='Blocked',
            is_active=True,
        )
        blocked = CustomerProfile.objects.create(
            user=blocked_user,
            phone='1713000044',
            is_email_verified=True,
            meal_service_blocked_low_balance=True,
        )
        self._seed_delivery(blocked, loc1, 'lunch')

        self._auth_rider()
        with patch(
            'delivery_zones.services.board.get_current_delivery_period',
            return_value=(self.service_date, OrderDelivery.MealPeriod.LUNCH),
        ):
            board = self.client.get(
                '/user_management/deliveryman/deliveries/today-board/'
            )
        self.assertEqual(board.status_code, status.HTTP_200_OK)
        self.assertEqual(board.data['total_count'], 1)
        self.assertEqual(board.data['periods']['lunch']['total_count'], 1)
        locations = board.data['periods']['lunch']['locations']
        self.assertEqual(len(locations), 1)
        self.assertEqual(locations[0]['delivery_count'], 1)
        phones = [row['customer_phone'] for row in locations[0]['customers']]
        self.assertEqual(phones, ['1713000001'])

    def test_deliveryman_board_all_blocked_yields_empty_period(self):
        self._auth_admin()
        zone1 = create_zone(name='Zone 1', code='zone-1', priority=1)
        loc1 = create_location(
            name='Chawkbazar', zone_public_id=zone1.public_id, priority=1
        )
        assign_delivery_man(zone1, delivery_man_public_id=self.rider.public_id)

        self.customer.meal_service_blocked_low_balance = True
        self.customer.save(update_fields=['meal_service_blocked_low_balance'])
        self._seed_delivery(self.customer, loc1, 'lunch')

        self._auth_rider()
        with patch(
            'delivery_zones.services.board.get_current_delivery_period',
            return_value=(self.service_date, OrderDelivery.MealPeriod.LUNCH),
        ):
            board = self.client.get(
                '/user_management/deliveryman/deliveries/today-board/'
            )
        self.assertEqual(board.status_code, status.HTTP_200_OK)
        self.assertEqual(board.data['active_meal_period'], 'lunch')
        self.assertEqual(board.data['zone']['code'], 'zone-1')
        self.assertEqual(board.data['total_count'], 0)
        self.assertEqual(board.data['periods']['lunch']['total_count'], 0)
        self.assertEqual(board.data['periods']['lunch']['locations'], [])

    def test_deliveryman_mark_delivery_zone_scoped_and_idempotent(self):
        self._auth_admin()
        zone1 = create_zone(name='Zone 1', code='zone-1', priority=1)
        zone2 = create_zone(name='Zone 2', code='zone-2', priority=2)
        loc1 = create_location(
            name='Chawkbazar', zone_public_id=zone1.public_id, priority=1
        )
        loc2 = create_location(
            name='Other', zone_public_id=zone2.public_id, priority=1
        )
        assign_delivery_man(zone1, delivery_man_public_id=self.rider.public_id)
        delivery = self._seed_delivery(self.customer, loc1, 'lunch')

        other_user = User.objects.create_user(
            username='dz_foreign',
            email='dz_foreign@example.com',
            password='StrongPassword123',
            is_active=True,
        )
        foreign_customer = CustomerProfile.objects.create(
            user=other_user,
            phone='1713000099',
            is_email_verified=True,
        )
        foreign = self._seed_delivery(foreign_customer, loc2, 'lunch')

        self._auth_rider()
        # Foreign zone denied
        denied = self.client.post(
            f'/user_management/deliveryman/deliveries/{foreign.public_id}/mark/',
            {'status': 'delivered'},
            format='json',
        )
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)

        with patch(
            'orders.services.order_delivery.charge_delivered_meal',
            return_value=None,
        ), patch(
            'notifications.services.meal_delivery_notifications.notify_meal_delivered',
            return_value=None,
        ):
            first = self.client.post(
                f'/user_management/deliveryman/deliveries/{delivery.public_id}/mark/',
                {'status': 'delivered'},
                format='json',
            )
            self.assertEqual(first.status_code, status.HTTP_200_OK)
            self.assertEqual(first.data['status'], 'delivered')

            second = self.client.post(
                f'/user_management/deliveryman/deliveries/{delivery.public_id}/mark/',
                {'status': 'delivered'},
                format='json',
            )
            self.assertEqual(second.status_code, status.HTTP_200_OK)
            self.assertEqual(second.data['status'], 'delivered')

        delivery.refresh_from_db()
        self.assertEqual(delivery.status, OrderDelivery.DeliveryStatus.DELIVERED)

    def test_deliveryman_mark_rejects_low_balance_blocked_customer(self):
        self._auth_admin()
        zone1 = create_zone(name='Zone 1', code='zone-1', priority=1)
        loc1 = create_location(
            name='Chawkbazar', zone_public_id=zone1.public_id, priority=1
        )
        assign_delivery_man(zone1, delivery_man_public_id=self.rider.public_id)

        self.customer.meal_service_blocked_low_balance = True
        self.customer.save(update_fields=['meal_service_blocked_low_balance'])
        delivery = self._seed_delivery(self.customer, loc1, 'lunch')

        self._auth_rider()
        with patch(
            'orders.services.order_delivery.charge_delivered_meal',
            return_value=None,
        ) as charge_mock:
            resp = self.client.post(
                f'/user_management/deliveryman/deliveries/{delivery.public_id}/mark/',
                {'status': 'delivered'},
                format='json',
            )
        self.assertEqual(resp.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(resp.data['error_code'], 'MEAL_SERVICE_BLOCKED_LOW_BALANCE')
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, OrderDelivery.DeliveryStatus.SCHEDULED)
        charge_mock.assert_not_called()

    def test_deliveryman_mark_then_auto_delivery_no_double_charge(self):
        from orders.services.auto_meal_delivery import run_auto_delivery

        self._auth_admin()
        zone1 = create_zone(name='Zone 1', code='zone-1', priority=1)
        loc1 = create_location(
            name='Chawkbazar', zone_public_id=zone1.public_id, priority=1
        )
        assign_delivery_man(zone1, delivery_man_public_id=self.rider.public_id)
        delivery = self._seed_delivery(self.customer, loc1, 'lunch')

        self._auth_rider()
        with patch(
            'orders.services.order_delivery.charge_delivered_meal',
            return_value=None,
        ), patch(
            'notifications.services.meal_delivery_notifications.notify_meal_delivered',
            return_value=None,
        ):
            first = self.client.post(
                f'/user_management/deliveryman/deliveries/{delivery.public_id}/mark/',
                {'status': 'delivered'},
                format='json',
            )
            self.assertEqual(first.status_code, status.HTTP_200_OK)

            result = run_auto_delivery(
                service_date=self.service_date,
                meal_period=OrderDelivery.MealPeriod.LUNCH,
                acquire_lock=False,
            )

        self.assertEqual(result.candidate_count, 0)
        self.assertEqual(result.delivered, 0)
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, OrderDelivery.DeliveryStatus.DELIVERED)

    def test_admin_mark_still_allows_low_balance_blocked_customer(self):
        from orders.services.order_delivery import mark_delivery

        self._auth_admin()
        zone1 = create_zone(name='Zone 1', code='zone-1', priority=1)
        loc1 = create_location(
            name='Chawkbazar', zone_public_id=zone1.public_id, priority=1
        )
        self.customer.meal_service_blocked_low_balance = True
        self.customer.save(update_fields=['meal_service_blocked_low_balance'])
        delivery = self._seed_delivery(self.customer, loc1, 'lunch')

        with patch(
            'orders.services.order_delivery.charge_delivered_meal',
            return_value=None,
        ):
            updated = mark_delivery(
                delivery,
                OrderDelivery.DeliveryStatus.DELIVERED,
                marked_by=self.admin_user,
            )
        self.assertEqual(updated.status, OrderDelivery.DeliveryStatus.DELIVERED)
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, OrderDelivery.DeliveryStatus.DELIVERED)

    def test_deliveryman_assign_zone_api(self):
        self._auth_admin()
        zone = create_zone(name='Zone 1', code='zone-1', priority=1)
        resp = self.client.patch(
            f'/user_management/admin/deliverymen/{self.rider.public_id}/assign-zone/',
            {'zone_public_id': str(zone.public_id)},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['assigned_zone']['public_id'], str(zone.public_id))
