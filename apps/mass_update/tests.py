from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import Tenant, User
from apps.clients.models import Counterparty, EconomicGroup


class MassUpdateTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Tenant Teste", slug="tenant-mass-update")
        self.user = User.objects.create_user(
            username="mass_update_user",
            email="mass_update@example.com",
            password="secret123",
            full_name="Mass Update User",
            tenant=self.tenant,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_apply_updates_only_records_matching_text_filters(self):
        matching_group = EconomicGroup.objects.create(tenant=self.tenant, grupo="Grupo Alvo")
        untouched_group = EconomicGroup.objects.create(tenant=self.tenant, grupo="Grupo Fora")
        self.user.accessible_groups.set([matching_group, untouched_group])

        response = self.client.post(
            "/api/mass-update/apply/",
            {
                "resource": "groups",
                "filters": [{"field": "grupo", "value": "Alvo"}],
                "updates": [{"field": "grupo", "toValue": "Grupo Atualizado", "matchCurrent": False, "fromValue": None, "clearTarget": False}],
                "search": "",
            },
            format="json",
            secure=True,
        )

        self.assertEqual(response.status_code, 200, getattr(response, "data", response.content))
        self.assertEqual(response.data["updatedCount"], 1)

        matching_group.refresh_from_db()
        untouched_group.refresh_from_db()
        self.assertEqual(matching_group.grupo, "Grupo Atualizado")
        self.assertEqual(untouched_group.grupo, "Grupo Fora")

    def test_apply_accepts_relation_labels_typed_in_open_inputs(self):
        allowed_group = EconomicGroup.objects.create(tenant=self.tenant, grupo="Grupo Permitido")
        self.user.accessible_groups.set([allowed_group])
        target_counterparty = Counterparty.objects.create(tenant=self.tenant, grupo=allowed_group, contraparte="Contraparte A", obs="Obs inicial")

        response = self.client.post(
            "/api/mass-update/apply/",
            {
                "resource": "counterparties",
                "filters": [{"field": "grupo", "value": "Grupo Permitido"}],
                "updates": [{"field": "grupo", "toValue": "Grupo Permitido", "matchCurrent": False, "fromValue": None, "clearTarget": False}],
                "search": "",
            },
            format="json",
            secure=True,
        )

        self.assertEqual(response.status_code, 200, getattr(response, "data", response.content))
        self.assertEqual(response.data["updatedCount"], 1)

        target_counterparty.refresh_from_db()
        self.assertEqual(target_counterparty.grupo_id, allowed_group.id)
