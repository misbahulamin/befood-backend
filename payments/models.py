from django.db import models
from orders.models import Order

class PaymentMethod(models.Model):
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    config = models.JSONField(default=dict, blank=True)

class PaymentIntent(models.Model):
    STATUS_CHOICES = [('initiated','Initiated'),('pending','Pending'),('success','Success'),('failed','Failed'),('cancelled','Cancelled')]
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='initiated')
    gateway_ref = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class PaymentTransaction(models.Model):
    intent = models.ForeignKey(PaymentIntent, on_delete=models.CASCADE)
    gateway_txn_id = models.CharField(max_length=255)
    status = models.CharField(max_length=50)
    raw_response = models.JSONField(default=dict, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

class PaymentWebhookLog(models.Model):
    gateway = models.CharField(max_length=100)
    payload = models.JSONField(default=dict, blank=True)
    processed = models.BooleanField(default=False)
    received_at = models.DateTimeField(auto_now_add=True)

class Refund(models.Model):
    transaction = models.ForeignKey(PaymentTransaction, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=50)
    processed_at = models.DateTimeField(null=True, blank=True)
