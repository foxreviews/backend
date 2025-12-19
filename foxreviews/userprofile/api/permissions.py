from rest_framework.permissions import BasePermission


class RolePermission(BasePermission):
    """Permission basée sur la liste allowed_roles définie sur la vue."""

    def has_permission(self, request, view):
        roles = getattr(view, "allowed_roles", None)
        if roles is None:
            return True
        return bool(
            request.user
            and request.user.is_authenticated
            and getattr(getattr(request.user, "profile", None), "role", None) in roles,
        )
