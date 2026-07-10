from rest_framework.permissions import BasePermission, IsAuthenticated

from user_management.services.admin_access import is_verified_admin


class IsVerifiedCustomer(IsAuthenticated):
    message = 'Email verification is required before placing an order.'

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False

        user = request.user
        if is_verified_admin(user):
            return True
        if user.is_superuser:
            return True

        profile = getattr(user, 'customer_profile', None)
        if profile is None or not profile.is_email_verified:
            return False

        return user.groups.filter(name='CUSTOMER').exists() or user.is_superuser


class IsOrderOwnerOrAdmin(BasePermission):
    def has_object_permission(self, request, view, obj):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if is_verified_admin(user) or user.is_superuser:
            return True
        return obj.customer.user_id == user.id
