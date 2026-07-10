import django_filters
from .models import DeliveryAssignment
class DeliveryAssignmentFilter(django_filters.FilterSet):
    class Meta: model = DeliveryAssignment; fields = ['rider','status']
