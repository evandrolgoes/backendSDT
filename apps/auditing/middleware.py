from .context import set_current_audit_user


class AuditUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        with set_current_audit_user(user if getattr(user, "is_authenticated", False) else None):
            return self.get_response(request)
