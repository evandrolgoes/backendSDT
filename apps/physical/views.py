from collections import defaultdict
from datetime import date
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from rest_framework import parsers, status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.auditing.context import suppress_audit_signals
from apps.auditing.models import Attachment
from apps.auditing.serializers import AttachmentSerializer
from apps.catalog.models import Exchange
from apps.core.viewsets import TenantScopedModelViewSet
from apps.marketdata.services import compute_sale_basis, get_ptax_usd_brl

from .models import ActualCost, BudgetCost, CashPayment, Custo, PhysicalPayment, PhysicalQuote, PhysicalSale
from .serializers import (
    ActualCostSerializer,
    BudgetCostSerializer,
    CashPaymentSerializer,
    CustoSerializer,
    PhysicalPaymentSerializer,
    PhysicalQuoteSerializer,
    PhysicalSaleSerializer,
)


class PhysicalQuoteViewSet(TenantScopedModelViewSet):
    queryset = PhysicalQuote.objects.select_related("tenant", "safra", "created_by").all()
    serializer_class = PhysicalQuoteSerializer
    filterset_fields = ["safra", "data_pgto", "data_report"]
    search_fields = ["cultura_texto", "localidade", "moeda_unidade", "obs"]


class BudgetCostViewSet(TenantScopedModelViewSet):
    queryset = BudgetCost.objects.select_related("tenant", "subgrupo", "grupo", "cultura", "safra", "created_by").all()
    serializer_class = BudgetCostSerializer
    filterset_fields = ["cultura", "safra", "considerar_na_politica_de_hedge", "moeda"]
    search_fields = ["grupo_despesa", "obs"]


class ActualCostViewSet(TenantScopedModelViewSet):
    queryset = ActualCost.objects.select_related("tenant", "subgrupo", "grupo", "cultura", "safra", "created_by").all()
    serializer_class = ActualCostSerializer
    filterset_fields = ["cultura", "safra", "moeda", "data_travamento"]
    search_fields = ["grupo_despesa", "obs"]


class CustoViewSet(TenantScopedModelViewSet):
    queryset = Custo.objects.select_related("tenant", "subgrupo", "grupo", "cultura", "safra", "created_by").all()
    serializer_class = CustoSerializer
    filterset_fields = ["grupo", "subgrupo", "cultura", "safra", "moeda", "data_realizado"]
    search_fields = ["descricao"]

    @action(detail=False, methods=["post"], url_path="importar-legado")
    def importar_legado(self, request):
        """Migração ÚNICA E PROVISÓRIA: copia BudgetCost (orçado) + ActualCost
        (realizado) para Custo, mesclando por chave.

        - Escopo: TODAS as carteiras (restrito a superuser).
        - Chave de mescla: tenant + grupo + subgrupo + cultura + safra + moeda
          + grupo_despesa (vira `descricao`). Linhas com a mesma chave somam
          `valor`; `data_realizado` = maior `data_travamento`; `obs` concatena.
        - Idempotente: re-rodar atualiza as mesmas linhas (não duplica). NÃO
          apaga BudgetCost/ActualCost — a remoção é feita depois, validada.
        - `considerar_na_politica_de_hedge` é descartado (não existe em Custo).
        """
        if not request.user.is_superuser:
            return Response(
                {"error": "Apenas superuser pode rodar a migração de custos legados."},
                status=status.HTTP_403_FORBIDDEN,
            )

        def _norm(value):
            return (value or "").strip()

        budget_agg = defaultdict(lambda: {"valor": Decimal("0"), "obs": []})
        for b in BudgetCost.objects.all().iterator():
            key = (b.tenant_id, b.grupo_id, b.subgrupo_id, b.cultura_id, b.safra_id, _norm(b.moeda), _norm(b.grupo_despesa))
            agg = budget_agg[key]
            if b.valor is not None:
                agg["valor"] += b.valor
            if _norm(b.obs):
                agg["obs"].append(b.obs.strip())

        actual_agg = defaultdict(lambda: {"valor": Decimal("0"), "data": None, "obs": []})
        for a in ActualCost.objects.all().iterator():
            key = (a.tenant_id, a.grupo_id, a.subgrupo_id, a.cultura_id, a.safra_id, _norm(a.moeda), _norm(a.grupo_despesa))
            agg = actual_agg[key]
            if a.valor is not None:
                agg["valor"] += a.valor
            if a.data_travamento and (agg["data"] is None or a.data_travamento > agg["data"]):
                agg["data"] = a.data_travamento
            if _norm(a.obs):
                agg["obs"].append(a.obs.strip())

        created = 0
        updated = 0
        all_keys = set(budget_agg) | set(actual_agg)

        with transaction.atomic(), suppress_audit_signals():
            for key in all_keys:
                tenant_id, grupo_id, subgrupo_id, cultura_id, safra_id, moeda, grupo_despesa = key
                b = budget_agg.get(key)
                a = actual_agg.get(key)

                seen = set()
                obs_list = []
                for part in (b["obs"] if b else []) + (a["obs"] if a else []):
                    if part not in seen:
                        seen.add(part)
                        obs_list.append(part)

                defaults = {
                    "valor_orcado": b["valor"] if b else None,
                    "valor_realizado": a["valor"] if a else None,
                    "data_realizado": a["data"] if a else None,
                    "obs": " | ".join(obs_list),
                }
                obj, was_created = Custo.objects.get_or_create(
                    tenant_id=tenant_id,
                    grupo_id=grupo_id,
                    subgrupo_id=subgrupo_id,
                    cultura_id=cultura_id,
                    safra_id=safra_id,
                    moeda=moeda,
                    descricao=grupo_despesa,
                    defaults=defaults,
                )
                if was_created:
                    created += 1
                else:
                    for field, value in defaults.items():
                        setattr(obj, field, value)
                    obj.save(update_fields=list(defaults.keys()))
                    updated += 1

        return Response(
            {
                "ok": True,
                "origem": {
                    "budget_costs": BudgetCost.objects.count(),
                    "actual_costs": ActualCost.objects.count(),
                },
                "linhas_chave": len(all_keys),
                "custos_criados": created,
                "custos_atualizados": updated,
                "total_custos": Custo.objects.count(),
            }
        )


class PhysicalSaleViewSet(TenantScopedModelViewSet):
    queryset = PhysicalSale.objects.select_related("tenant", "grupo", "subgrupo", "cultura", "safra", "contraparte", "created_by").all()
    serializer_class = PhysicalSaleSerializer
    filterset_fields = ["cultura", "safra", "contraparte", "compra_venda", "moeda_contrato", "moeda_unidade", "contrato_bolsa", "localidade"]
    search_fields = ["cultura_produto", "objetivo_venda_dolarizada", "localidade", "contrato_bolsa", "obs"]

    @action(detail=False, methods=["get"], url_path="basis")
    def basis(self, request):
        """Basis por venda para a bolsa de referência informada (`?bolsa=<nome>`).

        Respeita os mesmos filtros/busca do list. Lê do cache de cotações —
        a 1ª chamada esquenta o cache; as seguintes não fazem busca externa.
        """
        bolsa = request.query_params.get("bolsa", "").strip()
        if not bolsa:
            return Response({"error": "bolsa é obrigatório"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            exchange = Exchange.objects.get(nome__iexact=bolsa)
        except Exchange.DoesNotExist:
            return Response({"error": f"bolsa '{bolsa}' não encontrada"}, status=status.HTTP_404_NOT_FOUND)

        results = []
        for sale in self.filter_queryset(self.get_queryset()):
            data = compute_sale_basis(sale, exchange)
            results.append(
                {
                    "id": sale.id,
                    "basis": str(data["basis"]) if data else None,
                    "cotacao_bolsa": str(data["cotacao_bolsa"]) if data else None,
                    "fisico_convertido": str(data["fisico_convertido"]) if data else None,
                    "dolar_futuro": str(data["dolar_futuro"]) if data and data["dolar_futuro"] is not None else None,
                }
            )
        return Response({"bolsa": exchange.nome, "results": results})

    @action(detail=False, methods=["get"], url_path="ptax")
    def ptax(self, request):
        """PTAX USD/BRL (fechamento) por data — batch: `?dates=YYYY-MM-DD,YYYY-MM-DD`.

        Retorna `{ "YYYY-MM-DD": "5.1234" | null }`. Cacheado: cada data é
        buscada no BCB no máximo uma vez.
        """
        raw = request.query_params.get("dates", "").strip()
        if not raw:
            return Response({"error": "dates é obrigatório"}, status=status.HTTP_400_BAD_REQUEST)
        out = {}
        for token in {d.strip() for d in raw.split(",") if d.strip()}:
            try:
                day = date.fromisoformat(token)
            except ValueError:
                continue
            rate = get_ptax_usd_brl(day)
            out[token] = str(rate) if rate is not None else None
        return Response(out)

    @action(detail=True, methods=["get", "post"], parser_classes=[parsers.MultiPartParser, parsers.FormParser])
    def attachments(self, request, pk=None):
        instance = self.get_object()
        content_type = ContentType.objects.get_for_model(PhysicalSale)
        queryset = Attachment.objects.filter(
            tenant=instance.tenant,
            content_type=content_type,
            object_id=instance.pk,
        ).order_by("-created_at")

        if request.method == "GET":
            return Response(AttachmentSerializer(queryset, many=True, context={"request": request}).data)

        files = request.FILES.getlist("files")
        created = [
            Attachment.create_from_upload(
                tenant=instance.tenant,
                uploaded_by=request.user,
                content_type=content_type,
                object_id=instance.pk,
                uploaded_file=uploaded_file,
            )
            for uploaded_file in files
        ]
        return Response(AttachmentSerializer(created, many=True, context={"request": request}).data, status=status.HTTP_201_CREATED)


class PhysicalPaymentViewSet(TenantScopedModelViewSet):
    queryset = PhysicalPayment.objects.select_related("tenant", "grupo", "subgrupo", "fazer_frente_com", "safra", "contraparte", "created_by").all()
    serializer_class = PhysicalPaymentSerializer
    filterset_fields = ["fazer_frente_com", "safra", "contraparte", "unidade", "classificacao", "data_pagamento"]
    search_fields = ["descricao", "classificacao", "obs"]


class CashPaymentViewSet(TenantScopedModelViewSet):
    queryset = CashPayment.objects.select_related("tenant", "grupo", "subgrupo", "fazer_frente_com", "safra", "contraparte", "created_by").all()
    serializer_class = CashPaymentSerializer
    filterset_fields = ["grupo", "subgrupo", "contraparte", "status", "moeda", "data_vencimento", "data_pagamento"]
    search_fields = ["descricao", "contraparte_texto", "obs", "status"]
