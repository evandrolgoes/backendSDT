import json

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import Tenant, User
from apps.catalog.models import Currency, DerivativeOperationName, Exchange, PriceUnit, Unit
from apps.clients.models import Counterparty, CropSeason, EconomicGroup, SubGroup
from apps.derivatives.models import DerivativeOperation


class BubbleJsonImportTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Tenant Teste", slug="tenant-teste")
        self.user = User.objects.create_user(
            username="tester",
            email="tester@example.com",
            password="secret123",
            full_name="Tester",
            tenant=self.tenant,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_import_creates_missing_related_catalog_records_before_linking(self):
        payload = [
            {
                "_id": "DRV-IMPORT-001",
                "Grupo Origem": "Grupo Novo",
                "Subgrupo Origem": "Subgrupo Novo",
                "Ativo Origem": "Milho",
                "Safra Origem": "2026/27",
                "Contraparte Origem": "Contraparte Nova",
                "Bolsa Origem": "CME",
                "Strike Unidade Origem": "USD/sc",
                "Nome Operacao Origem": "NDF Custom",
                "Moeda Origem": "USD",
                "Unidade Origem": "sc",
            }
        ]
        mapping = {
            "Grupo Origem": "grupo",
            "Subgrupo Origem": "subgrupo",
            "Ativo Origem": "ativo",
            "Safra Origem": "safra",
            "Contraparte Origem": "contraparte",
            "Bolsa Origem": "bolsa_ref",
            "Strike Unidade Origem": "strike_moeda_unidade",
            "Nome Operacao Origem": "nome_da_operacao",
            "Moeda Origem": "volume_financeiro_moeda",
            "Unidade Origem": "volume_fisico_unidade",
        }

        response = self.client.post(
            "/api/import-tools/bubble/derivatives/",
            {
                "databaseTarget": "current",
                "destination": "derivatives",
                "rawJson": json.dumps(payload),
                "mapping": mapping,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["created"], 1)
        self.assertEqual(response.data["skipped"], 0)

        operation = DerivativeOperation.objects.get(cod_operacao_mae="DRV-IMPORT-001")
        self.assertEqual(operation.grupo.grupo, "Grupo Novo")
        self.assertEqual(operation.subgrupo.subgrupo, "Subgrupo Novo")
        self.assertEqual(operation.ativo.ativo, "Milho")
        self.assertEqual(operation.safra.safra, "2026/27")
        self.assertEqual(operation.contraparte.obs, "Contraparte Nova")
        self.assertEqual(operation.bolsa_ref, "CME")
        self.assertEqual(operation.strike_moeda_unidade, "USD/sc")
        self.assertEqual(operation.nome_da_operacao, "NDF Custom")
        self.assertEqual(operation.volume_financeiro_moeda, "USD")
        self.assertEqual(operation.volume_fisico_unidade, "sc")

        self.assertTrue(EconomicGroup.objects.filter(tenant=self.tenant, grupo="Grupo Novo").exists())
        self.assertTrue(SubGroup.objects.filter(tenant=self.tenant, subgrupo="Subgrupo Novo").exists())
        self.assertTrue(CropSeason.objects.filter(tenant=self.tenant, safra="2026/27").exists())
        self.assertTrue(Counterparty.objects.filter(tenant=self.tenant, obs="Contraparte Nova").exists())
        self.assertTrue(Exchange.objects.filter(nome="CME").exists())
        self.assertTrue(PriceUnit.objects.filter(nome="USD/sc").exists())
        self.assertTrue(DerivativeOperationName.objects.filter(nome="NDF Custom").exists())
        self.assertTrue(Currency.objects.filter(nome="USD").exists())
        self.assertTrue(Unit.objects.filter(nome="sc").exists())
