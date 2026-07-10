from rest_framework.permissions import BasePermission, IsAuthenticated


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
