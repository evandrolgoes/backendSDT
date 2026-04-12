from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import Tenant, User
from apps.clients.models import EconomicGroup
from apps.insights.models import MissingFieldIgnoredConfig


class MissingFieldsIgnoredConfigTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Tenant Teste", slug="tenant-teste")
        self.superuser = User.objects.create_superuser(
            username="root",
            email="root@example.com",
            password="secret123",
            tenant=self.tenant,
        )
        self.regular_user = User.objects.create_user(
            username="user",
            email="user@example.com",
            password="secret123",
            full_name="Usuario Teste",
            tenant=self.tenant,
        )
        self.client = APIClient()

    def test_superuser_can_configure_and_remove_ignored_fields(self):
        self.client.force_authenticate(user=self.superuser)

        config_response = self.client.get("/api/insights/missing-fields/ignored-config/")
        self.assertEqual(config_response.status_code, 200, config_response.data)
        self.assertTrue(any(item["resource"] == "groups" for item in config_response.data["resources"]))

        create_response = self.client.post(
            "/api/insights/missing-fields/ignored-config/",
            {"resource": "groups", "field_name": "grupo"},
            format="json",
        )
        self.assertIn(create_response.status_code, {200, 201}, create_response.data)
        self.assertTrue(
            MissingFieldIgnoredConfig.objects.filter(
                tenant=self.tenant,
                resource="groups",
                field_name="grupo",
            ).exists()
        )

        delete_response = self.client.delete(
            "/api/insights/missing-fields/ignored-config/",
            {"resource": "groups", "field_name": "grupo"},
            format="json",
        )
        self.assertEqual(delete_response.status_code, 200, delete_response.data)
        self.assertFalse(
            MissingFieldIgnoredConfig.objects.filter(
                tenant=self.tenant,
                resource="groups",
                field_name="grupo",
            ).exists()
        )

    def test_regular_user_cannot_manage_ignored_fields(self):
        self.client.force_authenticate(user=self.regular_user)

        response = self.client.get("/api/insights/missing-fields/ignored-config/")
        self.assertEqual(response.status_code, 403, response.data)

    def test_ignored_field_is_removed_from_missing_fields_report(self):
        EconomicGroup.objects.create(tenant=self.tenant, grupo="")
        self.client.force_authenticate(user=self.superuser)

        initial_response = self.client.get("/api/insights/missing-fields/")
        self.assertEqual(initial_response.status_code, 200, initial_response.data)
        self.assertTrue(
            any(row["resource"] == "groups" and "Grupo" in row["missing_fields"] for row in initial_response.data["rows"]),
            initial_response.data,
        )

        MissingFieldIgnoredConfig.objects.create(
            tenant=self.tenant,
            resource="groups",
            resource_label="Groups",
            field_name="grupo",
            field_label="Grupo",
        )

        filtered_response = self.client.get("/api/insights/missing-fields/")
        self.assertEqual(filtered_response.status_code, 200, filtered_response.data)
        self.assertFalse(
            any(row["resource"] == "groups" for row in filtered_response.data["rows"]),
            filtered_response.data,
        )
