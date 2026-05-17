from datetime import date

from django.contrib.contenttypes.models import ContentType
from rest_framework import parsers, status
from rest_framework.decorators import action
from rest_framework.response import Response

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
