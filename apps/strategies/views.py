import json
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import urlopen

from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from apps.core.viewsets import TenantScopedModelViewSet

from .models import CropBoard, HedgePolicy, Strategy, StrategyTrigger
from .serializers import CropBoardSerializer, HedgePolicySerializer, StrategySerializer, StrategyTriggerSerializer


IBGE_STATES_URL = "https://servicodados.ibge.gov.br/api/v1/localidades/estados?orderBy=nome"
IBGE_CITIES_URL = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios?orderBy=nome"


class StrategyViewSet(TenantScopedModelViewSet):
    queryset = Strategy.objects.select_related("tenant", "grupo", "subgrupo", "created_by").all()
    serializer_class = StrategySerializer
    filterset_fields = ["status"]
    search_fields = ["descricao_estrategia", "obs", "status"]


class StrategyTriggerViewSet(TenantScopedModelViewSet):
    queryset = StrategyTrigger.objects.select_related("tenant", "estrategia", "cultura").prefetch_related("grupos", "subgrupos").all()
    serializer_class = StrategyTriggerSerializer
    tenant_field = "tenant"
    filterset_fields = ["estrategia", "cultura", "status", "status_gatilho", "tipo", "tipo_fis_der", "posicao", "bolsa"]
    search_fields = ["contrato_derivativo", "contrato_bolsa", "codigo_derivativo", "bolsa", "produto_bolsa", "status", "obs"]


class HedgePolicyViewSet(TenantScopedModelViewSet):
    queryset = HedgePolicy.objects.select_related("tenant", "cultura", "safra", "created_by").prefetch_related("grupos", "subgrupos").all()
    serializer_class = HedgePolicySerializer
    filterset_fields = ["cultura", "safra"]
    search_fields = ["obs"]


class CropBoardViewSet(TenantScopedModelViewSet):
    queryset = CropBoard.objects.select_related("tenant", "grupo", "subgrupo", "cultura", "safra", "created_by").all()
    serializer_class = CropBoardSerializer
    filterset_fields = ["cultura", "safra", "monitorar_vc", "criar_politica_hedge"]
    search_fields = ["obs", "bolsa_ref", "unidade_producao", "localidade"]


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ibge_states(request):
    try:
        with urlopen(IBGE_STATES_URL, timeout=10) as response:
            payload = json.load(response)
    except (URLError, TimeoutError, ValueError):
        return JsonResponse([], safe=False, status=502)
    return JsonResponse(payload, safe=False)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ibge_cities(request):
    uf = (request.GET.get("uf") or "").strip().upper()
    if not uf:
        return JsonResponse({"detail": "Parametro uf e obrigatorio."}, status=400)

    try:
        with urlopen(IBGE_CITIES_URL.format(uf=quote(uf)), timeout=20) as response:
            payload = json.load(response)
    except (URLError, TimeoutError, ValueError):
        return JsonResponse([], safe=False, status=502)

    filtered = [
        city
        for city in payload
        if (
            city.get("microrregiao", {})
            .get("mesorregiao", {})
            .get("UF", {})
            .get("sigla", "")
            .upper()
            == uf
        )
    ]
    return JsonResponse(filtered, safe=False)
