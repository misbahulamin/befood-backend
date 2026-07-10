from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand
from business.models import BusinessProfile, BusinessSettings, Outlet
from user_management.models import CustomerProfile, RiderProfile, StaffProfile

class Command(BaseCommand):
    help = 'Seed Befood demo data'
    def handle(self, *args, **options):
        for name in ['CUSTOMER','RIDER','KITCHEN_STAFF','OUTLET_MANAGER','ADMIN']:
            Group.objects.get_or_create(name=name)
        admin, _ = User.objects.get_or_create(username='admin', defaults={'email':'admin@befood.local','is_superuser':True,'is_staff':True})
        admin.email='admin@befood.local'; admin.is_staff=True; admin.is_superuser=True; admin.set_password('admin12345'); admin.save()
        business, _ = BusinessProfile.objects.get_or_create(name='Befood-Bachelors E-Food')
        outlet, _ = Outlet.objects.get_or_create(business=business, name='Befood Main Outlet', defaults={'address':'Dhaka, Bangladesh'})
        BusinessSettings.objects.get_or_create(outlet=outlet, defaults={'min_order_amount':100, 'tax_rate':5, 'default_delivery_fee':30})
        customer, _ = User.objects.get_or_create(username='customer1', defaults={'email':'customer1@befood.local'})
        customer.set_password('customer12345'); customer.save(); CustomerProfile.objects.get_or_create(user=customer)
        rider, _ = User.objects.get_or_create(username='rider1', defaults={'email':'rider1@befood.local'})
        rider.set_password('rider12345'); rider.save(); RiderProfile.objects.get_or_create(user=rider)
        kitchen, _ = User.objects.get_or_create(username='kitchen1', defaults={'email':'kitchen1@befood.local'})
        kitchen.set_password('kitchen12345'); kitchen.save(); StaffProfile.objects.get_or_create(user=kitchen, defaults={'outlet': outlet, 'role': 'kitchen'})
        self.stdout.write(self.style.SUCCESS('Seed completed'))
