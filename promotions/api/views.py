from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from promotions.models import Coupon, CouponUsage, Promotion
from .serializers import CouponSerializer, CouponUsageSerializer, PromotionSerializer

class CouponViewSet(viewsets.ModelViewSet):
    queryset = Coupon.objects.all()
    serializer_class = CouponSerializer
    permission_classes = [IsAuthenticated]

class CouponUsageViewSet(viewsets.ModelViewSet):
    queryset = CouponUsage.objects.all()
    serializer_class = CouponUsageSerializer
    permission_classes = [IsAuthenticated]

class PromotionViewSet(viewsets.ModelViewSet):
    queryset = Promotion.objects.all()
    serializer_class = PromotionSerializer
    permission_classes = [IsAuthenticated]
