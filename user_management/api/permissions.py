from rest_framework.permissions import BasePermission, IsAuthenticated

from user_management.services.admin_access import is_verified_admin


class HasCustomerProfile(IsAuthenticated):
    message = 'Customer profile not found for this account.'

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        return hasattr(request.user, 'customer_profile')


class IsCustomerAddressOwner(BasePermission):
    message = 'You do not have permission to access this address.'

    def has_object_permission(self, request, view, obj):
        profile = getattr(request.user, 'customer_profile', None)
        if profile is None:
            return False
        return obj.customer_profile_id == profile.id


class IsCustomerDeliveryPlaceOwner(BasePermission):
    message = 'You do not have permission to access this delivery place.'

    def has_object_permission(self, request, view, obj):
        profile = getattr(request.user, 'customer_profile', None)
        if profile is None:
            return False
        return obj.customer_profile_id == profile.id


class IsVerifiedAdmin(IsAuthenticated):
    message = 'Verified admin access required.'

    def has_permission(self, request, view):
        return super().has_permission(request, view) and is_verified_admin(request.user)


class IsVerifiedDeliveryman(IsAuthenticated):
    message = 'Verified delivery man access required.'

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if not request.user.is_active:
            return False
        profile = getattr(request.user, 'rider_profile', None)
        return profile is not None and profile.is_verified
