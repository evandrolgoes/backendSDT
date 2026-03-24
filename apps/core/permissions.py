from rest_framework.permissions import BasePermission


class IsMasterAdminOrTenantUser(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)


class IsMasterAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_superuser)


class IsMasterAdminOrTenantManager(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and (user.is_superuser or getattr(user, "is_tenant_admin", lambda: False)()))


class IsMasterAdminOrTenantAdmin(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (
                user.is_superuser
                or getattr(user, "is_tenant_admin", lambda: False)()
            )
        )


class IsMasterAdminOrAdminTenantAdmin(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (
                user.is_superuser
                or (getattr(user, "is_tenant_admin", lambda: False)() and getattr(user, "has_tenant_slug", lambda *args: False)("admin"))
            )
        )


class IsMasterAdminOrInvitationTenantAdmin(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (
                user.is_superuser
                or (
                    getattr(user, "is_tenant_admin", lambda: False)()
                    and getattr(getattr(user, "tenant", None), "can_send_invitations", False)
                )
            )
        )


class IsMasterAdminOrTenantCanManageGroups(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (
                user.is_superuser
                or (
                    getattr(user, "is_tenant_admin", lambda: False)()
                    and getattr(getattr(user, "tenant", None), "can_register_groups", False)
                )
            )
        )


class IsMasterAdminOrTenantCanManageSubgroups(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (
                user.is_superuser
                or (
                    getattr(user, "is_tenant_admin", lambda: False)()
                    and getattr(getattr(user, "tenant", None), "can_register_subgroups", False)
                )
            )
        )
