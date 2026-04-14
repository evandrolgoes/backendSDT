from django.db import models


class TableColumnConfig(models.Model):
    tenant = models.ForeignKey(
        "accounts.Tenant",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="table_column_configs",
    )
    resource = models.CharField(max_length=120)
    ordered_keys = models.JSONField(default=list)
    hidden_keys = models.JSONField(default=list)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("tenant", "resource")]
        indexes = [
            models.Index(fields=["tenant"]),
            models.Index(fields=["tenant", "resource"]),
        ]

    def __str__(self):
        return f"{self.resource} (tenant={self.tenant_id})"


class MissingFieldIgnoredConfig(models.Model):
    tenant = models.ForeignKey(
        "accounts.Tenant",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="missing_field_ignored_configs",
    )
    resource = models.CharField(max_length=120)
    resource_label = models.CharField(max_length=160, blank=True)
    field_name = models.CharField(max_length=120)
    field_label = models.CharField(max_length=160, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["resource_label", "field_label", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "resource", "field_name"],
                name="uq_missing_field_ignored_config_scope",
            )
        ]
        indexes = [
            models.Index(fields=["tenant", "resource"]),
            models.Index(fields=["tenant", "field_name"]),
        ]

    def __str__(self):
        resource_label = self.resource_label or self.resource
        field_label = self.field_label or self.field_name
        return f"{resource_label}: {field_label}"
