from rest_framework import viewsets


class TenantScopedModelViewSet(viewsets.ModelViewSet):
    tenant_field = "tenant"

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.is_superuser:
            return queryset
        if hasattr(queryset.model, self.tenant_field):
            return queryset.filter(**{self.tenant_field: user.tenant})
        return queryset

    def perform_create(self, serializer):
        extra = {}
        model = serializer.Meta.model
        if hasattr(model, "tenant") and not self.request.user.is_superuser:
            extra["tenant"] = self.request.user.tenant
        if hasattr(model, "created_by"):
            extra["created_by"] = self.request.user
        serializer.save(**extra)
