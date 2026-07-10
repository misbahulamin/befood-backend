from django.db import models
from business.models import Outlet, DeliveryZone
from user_management.models import RiderProfile
from orders.models import Order

class RiderLocation(models.Model):
    rider = models.ForeignKey(RiderProfile, on_delete=models.CASCADE)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    timestamp = models.DateTimeField(auto_now_add=True)

class DeliveryAssignment(models.Model):
    STATUS_CHOICES = [('assigned','Assigned'),('picked_up','Picked up'),('delivered','Delivered'),('cancelled','Cancelled')]
    order = models.OneToOneField(Order, on_delete=models.CASCADE)
    rider = models.ForeignKey(RiderProfile, on_delete=models.CASCADE)
    assigned_at = models.DateTimeField(auto_now_add=True)
    picked_up_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='assigned')

class DeliveryTracking(models.Model):
    assignment = models.ForeignKey(DeliveryAssignment, on_delete=models.CASCADE)
    checkpoint = models.CharField(max_length=255)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    timestamp = models.DateTimeField(auto_now_add=True)

class DeliveryFeeRule(models.Model):
    outlet = models.ForeignKey(Outlet, on_delete=models.CASCADE)
    zone = models.ForeignKey(DeliveryZone, on_delete=models.CASCADE)
    base_fee = models.DecimalField(max_digits=10, decimal_places=2)
    per_km_fee = models.DecimalField(max_digits=10, decimal_places=2)
    free_above_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
