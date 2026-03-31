from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import Tenant, User
from apps.market_summary.services import DEFAULT_MARKET_SUMMARY_SOURCES, generate_market_summary


class MarketSummaryGenerateViewTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Tenant Teste", slug="tenant-teste")
        self.superuser = User.objects.create_superuser(
            username="root",
            email="root@example.com",
            password="secret123",
        )
        self.user = User.objects.create_user(
            username="user",
            email="user@example.com",
            password="secret123",
            full_name="Usuario Teste",
            tenant=self.tenant,
        )
        self.client = APIClient()

    @patch("apps.market_summary.views.generate_market_summary")
    def test_superuser_can_generate_market_summary(self, mocked_generate):
        mocked_generate.return_value = {
            "summary": "# Resumo semanal",
            "model": "gpt-5-mini",
            "warnings": [],
            "source_count": 1,
            "use_source_search": True,
        }
        self.client.force_authenticate(user=self.superuser)

        response = self.client.post(
            "/api/market-summary/generate/",
            {
                "objective": "Gerar resumo semanal",
                "outline": "Principais Acontecimentos da Semana",
                "use_source_search": True,
                "sources": [{"title": "Fonte 1", "url": "https://example.com/noticias/", "content": ""}],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["summary"], "# Resumo semanal")
        mocked_generate.assert_called_once()

    def test_non_superuser_is_blocked(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/market-summary/generate/",
            {
                "sources": [{"title": "Fonte 1", "content": "Mercado firme na semana."}],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403, response.data)


class MarketSummaryServiceTests(TestCase):
    @patch("apps.market_summary.services._call_openai_market_summary")
    @patch("apps.market_summary.services._fetch_public_source_digest")
    def test_generate_uses_source_search_when_enabled(self, mocked_fetch, mocked_openai):
        mocked_fetch.return_value = "Noticias recentes coletadas automaticamente."
        mocked_openai.return_value = {"model": "gpt-5-mini", "summary": "## Resumo"}

        payload = generate_market_summary(
            {
                "sources": [{"title": "Noticias Agricolas", "url": "https://www.noticiasagricolas.com.br/noticias/", "content": ""}],
                "use_source_search": True,
            }
        )

        self.assertEqual(payload["summary"], "## Resumo")
        self.assertTrue(payload["use_source_search"])
        self.assertTrue(any("coletadas automaticamente" in item for item in payload["warnings"]))
        mocked_fetch.assert_called_once()

    @patch("apps.market_summary.services._call_openai_market_summary")
    @patch("apps.market_summary.services._hydrate_known_sources")
    def test_generate_uses_default_sources_when_none_are_sent(self, mocked_hydrate, mocked_openai):
        mocked_hydrate.side_effect = lambda sources, warnings, use_source_search=False: [
            {**item, "content": item.get("content") or "Conteudo coletado"}
            for item in sources
        ]
        mocked_openai.return_value = {"model": "gpt-5-mini", "summary": "## Resumo"}

        payload = generate_market_summary({})

        self.assertEqual(payload["summary"], "## Resumo")
        self.assertEqual(payload["source_count"], len(DEFAULT_MARKET_SUMMARY_SOURCES))
        mocked_hydrate.assert_called_once()

    @patch("apps.market_summary.services._call_openai_market_summary")
    def test_generate_warns_when_only_url_is_informed_without_search(self, mocked_openai):
        mocked_openai.return_value = {"model": "gpt-5-mini", "summary": "## Resumo"}

        payload = generate_market_summary(
            {
                "sources": [{"title": "Fonte 1", "url": "https://example.com/noticias/", "content": "Resumo manual"}],
                "use_source_search": False,
            }
        )

        self.assertEqual(payload["summary"], "## Resumo")
        self.assertEqual(payload["warnings"], [])

        with self.assertRaisesMessage(
            ValueError,
            "Nao encontrei conteudo suficiente nas fontes. Cole anotacoes manualmente ou ative a busca automatica.",
        ):
            generate_market_summary(
                {
                    "sources": [{"title": "Fonte 1", "url": "https://example.com/noticias/", "content": "   "}],
                    "use_source_search": False,
                }
            )
