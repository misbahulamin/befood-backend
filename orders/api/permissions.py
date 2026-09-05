from rest_framework.permissions import BasePermission, IsAuthenticated

from user_management.services.admin_access import is_verified_admin
from user_management.services.identity_verification import (
    IDENTITY_VERIFICATION_REQUIRED_MESSAGE,
    is_customer_identity_verified,
)


class IsVerifiedCustomer(IsAuthenticated):
    message = IDENTITY_VERIFICATION_REQUIRED_MESSAGE

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False

        user = request.user
        if is_verified_admin(user):
            return True
        if user.is_superuser:
            return True

        if not is_customer_identity_verified(user):
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
