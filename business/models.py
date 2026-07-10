from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class BusinessProfile(TimeStampedModel):
    name = models.CharField(max_length=255)
    logo = models.ImageField(upload_to='business/', blank=True, null=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=30, blank=True)
    description = models.TextField(blank=True)


class Outlet(TimeStampedModel):
    business = models.ForeignKey(BusinessProfile, on_delete=models.CASCADE, related_name='outlets')
    name = models.CharField(max_length=255)
    address = models.TextField()
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    phone = models.CharField(max_length=30, blank=True)


class OperatingHours(models.Model):
    outlet = models.ForeignKey(Outlet, on_delete=models.CASCADE, related_name='operating_hours')
    day_of_week = models.PositiveSmallIntegerField()
    open_time = models.TimeField()
    close_time = models.TimeField()
    is_closed = models.BooleanField(default=False)


class DeliveryZone(models.Model):
    outlet = models.ForeignKey(Outlet, on_delete=models.CASCADE, related_name='delivery_zones')
    name = models.CharField(max_length=100)
    radius_km = models.DecimalField(max_digits=6, decimal_places=2)
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)


class BusinessSettings(models.Model):
    outlet = models.OneToOneField(Outlet, on_delete=models.CASCADE, related_name='settings')
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    default_delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
