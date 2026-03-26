from django.contrib.contenttypes.models import ContentType
from rest_framework import parsers, status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.auditing.models import Attachment
from apps.auditing.serializers import AttachmentSerializer
from apps.core.viewsets import TenantScopedModelViewSet

from .models import ActualCost, BudgetCost, CashPayment, PhysicalPayment, PhysicalQuote, PhysicalSale
from .serializers import (
    ActualCostSerializer,
    BudgetCostSerializer,
    CashPaymentSerializer,
    PhysicalPaymentSerializer,
    PhysicalQuoteSerializer,
    PhysicalSaleSerializer,
)


class PhysicalQuoteViewSet(TenantScopedModelViewSet):
    queryset = PhysicalQuote.objects.select_related("tenant", "safra", "created_by").all()
    serializer_class = PhysicalQuoteSerializer
    filterset_fields = ["tenant", "safra", "data_pgto", "data_report"]
    search_fields = ["cultura_texto", "localidade", "moeda_unidade", "obs"]


class BudgetCostViewSet(TenantScopedModelViewSet):
    queryset = BudgetCost.objects.select_related("tenant", "subgrupo", "grupo", "cultura", "safra", "created_by").all()
    serializer_class = BudgetCostSerializer
    filterset_fields = ["tenant", "subgrupo", "grupo", "cultura", "safra", "considerar_na_politica_de_hedge", "moeda"]
    search_fields = ["grupo_despesa", "obs"]


class ActualCostViewSet(TenantScopedModelViewSet):
    queryset = ActualCost.objects.select_related("tenant", "subgrupo", "grupo", "cultura", "safra", "created_by").all()
    serializer_class = ActualCostSerializer
    filterset_fields = ["tenant", "subgrupo", "grupo", "cultura", "safra", "moeda"]
    search_fields = ["grupo_despesa", "obs"]


class PhysicalSaleViewSet(TenantScopedModelViewSet):
    queryset = PhysicalSale.objects.select_related("tenant", "grupo", "subgrupo", "cultura", "safra", "contraparte", "created_by").all()
    serializer_class = PhysicalSaleSerializer
    filterset_fields = ["tenant", "grupo", "subgrupo", "cultura", "safra", "contraparte", "compra_venda", "moeda_contrato", "moeda_unidade", "bolsa_ref", "contrato_bolsa", "localidade"]
    search_fields = ["cultura_produto", "objetivo_venda_dolarizada", "localidade", "contrato_bolsa", "obs"]

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
            return Response(AttachmentSerializer(queryset, many=True).data)

        files = request.FILES.getlist("files")
        created = [
            Attachment.objects.create(
                tenant=instance.tenant,
                uploaded_by=request.user,
                content_type=content_type,
                object_id=instance.pk,
                file=uploaded_file,
                original_name=uploaded_file.name,
            )
            for uploaded_file in files
        ]
        return Response(AttachmentSerializer(created, many=True).data, status=status.HTTP_201_CREATED)


class PhysicalPaymentViewSet(TenantScopedModelViewSet):
    queryset = PhysicalPayment.objects.select_related("tenant", "grupo", "subgrupo", "fazer_frente_com", "safra", "contraparte", "created_by").all()
    serializer_class = PhysicalPaymentSerializer
    filterset_fields = ["tenant", "grupo", "subgrupo", "fazer_frente_com", "safra", "contraparte", "unidade", "data_pagamento"]
    search_fields = ["descricao"]


class CashPaymentViewSet(TenantScopedModelViewSet):
    queryset = CashPayment.objects.select_related("tenant", "grupo", "subgrupo", "fazer_frente_com", "safra", "contraparte", "created_by").all()
    serializer_class = CashPaymentSerializer
    filterset_fields = ["tenant", "grupo", "subgrupo", "fazer_frente_com", "safra", "contraparte", "moeda", "data_pagamento"]
    search_fields = ["descricao"]
