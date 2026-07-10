from rest_framework.permissions import BasePermission


class HasGroupPermission(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        if hasattr(view, 'required_groups') and view.required_groups:
            return user.groups.filter(name__in=view.required_groups).exists()
        return True


class PermissionAwareMetadata:
    action_permission_map = {'list': 'view', 'retrieve': 'view', 'create': 'add', 'update': 'change', 'partial_update': 'change', 'destroy': 'delete'}
