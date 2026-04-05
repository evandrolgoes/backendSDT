import urllib.parse
import urllib.request
import csv
import io
import json
from datetime import timedelta

from django.http import JsonResponse, HttpResponse
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from rest_framework import parsers, status
from rest_framework.decorators import action
from rest_framework.permissions import BasePermission, SAFE_METHODS
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.auditing.context import suppress_audit_signals
from apps.auditing.models import Attachment
from apps.auditing.serializers import AttachmentSerializer
from apps.core.viewsets import TenantScopedModelViewSet

from .models import MarketNewsPost
from .serializers import MarketNewsPostListSerializer, MarketNewsPostSerializer
from .services import build_fund_position_payload


def mercado_health(_request):
    return JsonResponse({"status": "ok", "app": "mercado"})


YAHOO_SYMBOL_ALIASES = {
    "ZS1!": "ZS=F",
    "ZS=F": "ZS=F",
    "ZC=F": "ZC=F",
    "ZW=F": "ZW=F",
    "ZM=F": "ZM=F",
    "ZL=F": "ZL=F",
    "SB=F": "SB=F",
    "KC=F": "KC=F",
    "CC=F": "CC=F",
    "CT=F": "CT=F",
    "LE=F": "LE=F",
    "GF=F": "GF=F",
    "HE=F": "HE=F",
    "CL=F": "CL=F",
    "BZ=F": "BZ=F",
    "GC=F": "GC=F",
    "SI=F": "SI=F",
    "BRL=X": "BRL=X",
    "USDBRL": "BRL=X",
    "USDBRL=X": "BRL=X",
}

FRED_SERIES_ALIASES = {
    "DGS1": "DGS1",
    "DGS2": "DGS2",
    "DGS3": "DGS3",
    "DGS5": "DGS5",
    "DGS10": "DGS10",
    "US01Y": "DGS1",
    "US02Y": "DGS2",
    "US03Y": "DGS3",
    "US05Y": "DGS5",
    "US10Y": "DGS10",
}

WGB_COUNTRY_ALIASES = {
    "BRAZIL": {
        "symbol": "7",
        "name": "Brazil",
        "flag": "br",
        "url_page": "brazil",
    },
    "UNITED_STATES": {
        "symbol": "6",
        "name": "United States",
        "flag": "us",
        "url_page": "united-states",
    },
    "USA": {
        "symbol": "6",
        "name": "United States",
        "flag": "us",
        "url_page": "united-states",
    },
}

WGB_DURATION_ALIASES = {
    "1Y": {"label": "1 Year", "months": 12},
    "2Y": {"label": "2 Years", "months": 24},
    "3Y": {"label": "3 Years", "months": 36},
    "5Y": {"label": "5 Years", "months": 60},
    "10Y": {"label": "10 Years", "months": 120},
}

BRAZIL_MACRO_SYMBOL_ALIASES = {
    "BRINTR": "BRINTR",
    "BRGDPYY": "BRGDPYY",
}


def _iso_to_brazil_date(iso_date):
    year, month, day = str(iso_date or "").split("-")
    return f"{day}/{month}/{year}"


def _brazil_to_iso_date(brazil_date):
    day, month, year = str(brazil_date or "").split("/")
    return f"{year}-{month}-{day}"


def _quarter_code_to_iso_date(quarter_code):
    code = str(quarter_code or "").strip()
    if len(code) != 6 or not code.isdigit():
        raise ValueError("Invalid quarter code")

    quarter = int(code[-2:])
    if quarter == 1:
        return f"{code[:4]}-03-31"
    if quarter == 2:
        return f"{code[:4]}-06-30"
    if quarter == 3:
        return f"{code[:4]}-09-30"
    if quarter == 4:
        return f"{code[:4]}-12-31"
    raise ValueError("Invalid quarter code")


def yahoo_finance_proxy(request):
    requested_symbol = request.GET.get("symbol", "").strip().upper()
    period1 = request.GET.get("period1", "").strip()
    period2 = request.GET.get("period2", "").strip()
    symbol = YAHOO_SYMBOL_ALIASES.get(requested_symbol, "")

    if not requested_symbol or not period1 or not period2:
        return JsonResponse({"error": "Missing parameters"}, status=400)

    if not symbol:
        return JsonResponse({"error": "Symbol not allowed"}, status=400)

    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}"
        f"?period1={period1}&period2={period2}&interval=1d&includePrePost=false&events=history"
    )

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as response:
            data = response.read()
        return HttpResponse(data, content_type="application/json")
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=502)


def fred_proxy(request):
    requested_series = request.GET.get("series", "").strip().upper()
    start_date = request.GET.get("start_date", "").strip()
    end_date = request.GET.get("end_date", "").strip()
    fred_series = FRED_SERIES_ALIASES.get(requested_series, "")

    if not requested_series:
        return JsonResponse({"error": "Missing parameters"}, status=400)

    if not fred_series:
        return JsonResponse({"error": "Series not allowed"}, status=400)

    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={urllib.parse.quote(fred_series)}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as response:
            raw_csv = response.read().decode("utf-8", errors="replace")

        reader = csv.DictReader(io.StringIO(raw_csv))
        rows = []
        for row in reader:
            date = str(row.get("DATE") or "").strip()
            value = str(row.get(fred_series) or "").strip()
            if not date or not value or value == ".":
                continue
            if start_date and date < start_date:
                continue
            if end_date and date > end_date:
                continue
            try:
                numeric_value = float(value)
            except ValueError:
                continue
            rows.append({"date": date, "value": numeric_value})

        return JsonResponse({"series": requested_series, "source_series": fred_series, "rows": rows})
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=502)


def government_bond_proxy(request):
    requested_country = request.GET.get("country", "").strip().upper()
    requested_duration = request.GET.get("duration", "").strip().upper()
    start_date = request.GET.get("start_date", "").strip()
    end_date = request.GET.get("end_date", "").strip()

    country = WGB_COUNTRY_ALIASES.get(requested_country)
    duration = WGB_DURATION_ALIASES.get(requested_duration)

    if not requested_country or not requested_duration:
        return JsonResponse({"error": "Missing parameters"}, status=400)

    if not country or not duration:
        return JsonResponse({"error": "Country or duration not allowed"}, status=400)

    payload = {
        "GLOBALVAR": {
            "JS_VARIABLE": "jsGlobalVars",
            "FUNCTION": "Bond",
            "DOMESTIC": True,
            "ENDPOINT": "https://www.worldgovernmentbonds.com/wp-json/common/v1/historical",
            "DATE_RIF": "2099-12-31",
            "OBJ": {"UNIT": "%", "DECIMAL": 3, "UNIT_DELTA": "bp", "DECIMAL_DELTA": 1},
            "COUNTRY1": {
                "SYMBOL": country["symbol"],
                "PAESE": country["name"],
                "PAESE_UPPERCASE": country["name"].upper(),
                "BANDIERA": country["flag"],
                "URL_PAGE": country["url_page"],
            },
            "COUNTRY2": None,
            "OBJ1": {"DURATA_STRING": duration["label"], "DURATA": duration["months"]},
            "OBJ2": None,
        }
    }

    try:
        req = urllib.request.Request(
            "https://www.worldgovernmentbonds.com/wp-json/common/v1/historical",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "User-Agent": "Mozilla/5.0",
                "Content-Type": "application/json",
                "Origin": "https://www.worldgovernmentbonds.com",
                "Referer": f"https://www.worldgovernmentbonds.com/bond-historical-data/{country['url_page']}/{requested_duration.lower().replace('y', '-year/')}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=20) as response:
            raw_payload = json.loads(response.read().decode("utf-8"))

        raw_rows = raw_payload.get("result", {}).get("quote", {})
        rows = []
        for item in raw_rows.values():
            date = str(item.get("DATA_VAL") or "").strip()
            value = item.get("CLOSE_VAL")
            if not date or value in (None, ""):
                continue
            if start_date and date < start_date:
                continue
            if end_date and date > end_date:
                continue
            try:
                numeric_value = float(value)
            except (TypeError, ValueError):
                continue
            rows.append({"date": date, "value": numeric_value})

        return JsonResponse(
            {
                "country": requested_country,
                "duration": requested_duration,
                "source": "worldgovernmentbonds",
                "rows": rows,
            }
        )
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=502)


def brazil_macro_proxy(request):
    requested_symbol = request.GET.get("symbol", "").strip().upper()
    start_date = request.GET.get("start_date", "").strip()
    end_date = request.GET.get("end_date", "").strip()
    symbol = BRAZIL_MACRO_SYMBOL_ALIASES.get(requested_symbol, "")

    if not requested_symbol:
        return JsonResponse({"error": "Missing parameters"}, status=400)

    if not symbol:
        return JsonResponse({"error": "Symbol not allowed"}, status=400)

    try:
        if symbol == "BRINTR":
            today = timezone.now().date()
            default_start = today - timedelta(days=365 * 10)
            normalized_start = start_date or default_start.isoformat()
            normalized_end = end_date or today.isoformat()
            url = (
                "https://api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados"
                f"?formato=json&dataInicial={urllib.parse.quote(_iso_to_brazil_date(normalized_start))}"
                f"&dataFinal={urllib.parse.quote(_iso_to_brazil_date(normalized_end))}"
            )
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))

            rows = []
            for item in payload:
                date = _brazil_to_iso_date(item.get("data"))
                value = item.get("valor")
                if not date or value in (None, ""):
                    continue
                try:
                    numeric_value = float(str(value).replace(",", "."))
                except (TypeError, ValueError):
                    continue
                rows.append({"date": date, "value": numeric_value})

            return JsonResponse({"symbol": symbol, "source": "bcb_sgs_432", "rows": rows})

        req = urllib.request.Request(
            "https://servicodados.ibge.gov.br/api/v1/portal/indicadores?periodo=-40",
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(req, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))

        indicators = payload.get("5932", [])
        target_series = next((item for item in indicators if str(item.get("idVariavel")) == "6561"), None)
        if not target_series:
            return JsonResponse({"error": "Series not available"}, status=502)

        rows = []
        for quarter_code, value in (target_series.get("resultados") or {}).items():
            try:
                date = _quarter_code_to_iso_date(quarter_code)
                numeric_value = float(str(value).replace(",", "."))
            except (TypeError, ValueError):
                continue
            except ValueError:
                continue
            if start_date and date < start_date:
                continue
            if end_date and date > end_date:
                continue
            rows.append({"date": date, "value": numeric_value})

        return JsonResponse({"symbol": symbol, "source": "ibge_portal_5932_6561", "rows": rows})
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=502)


class FundPositionSeriesView(APIView):
    def get(self, request, *args, **kwargs):
        series_id = request.query_params.get("series", "soja")
        try:
            payload = build_fund_position_payload(series_id=series_id)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except RuntimeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response(payload, status=status.HTTP_200_OK)


class MarketNewsPostPermission(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated and (user.is_superuser or user.is_tenant_admin()))


class MarketNewsPostViewSet(TenantScopedModelViewSet):
    queryset = MarketNewsPost.objects.select_related("tenant", "created_by", "published_by").all()
    serializer_class = MarketNewsPostSerializer
    permission_classes = [MarketNewsPostPermission]
    filterset_fields = ["status_artigo", "published_by"]
    search_fields = ["titulo", "categorias", "conteudo_html"]

    def get_serializer_class(self):
        if self.action == "list":
            return MarketNewsPostListSerializer
        return super().get_serializer_class()

    def get_queryset(self):
        queryset = self.queryset.all()
        user = getattr(self.request, "user", None)
        public_read = str(self.request.query_params.get("public", "")).strip().lower() in {"1", "true", "yes"}
        if public_read:
            queryset = queryset.filter(status_artigo=MarketNewsPost.STATUS_PUBLISHED)
        elif not user or not user.is_authenticated:
            queryset = queryset.filter(status_artigo=MarketNewsPost.STATUS_PUBLISHED)
        else:
            queryset = super().get_queryset()
            if not (user.is_superuser or user.is_tenant_admin()):
                queryset = queryset.filter(status_artigo=MarketNewsPost.STATUS_PUBLISHED)

        if self.action == "list":
            queryset = queryset.defer("conteudo_html")
        return queryset

    def _build_save_kwargs(self, serializer):
        save_kwargs = {}
        if hasattr(serializer.Meta.model, "tenant"):
            save_kwargs["tenant"] = self.request.user.tenant
        if hasattr(serializer.Meta.model, "created_by") and serializer.instance is None:
            save_kwargs["created_by"] = self.request.user
        if serializer.validated_data.get("status_artigo") != MarketNewsPost.STATUS_PUBLISHED:
            return save_kwargs

        instance = serializer.instance
        if not getattr(instance, "data_publicacao", None) and not serializer.validated_data.get("data_publicacao"):
            save_kwargs["data_publicacao"] = timezone.now()
        if not getattr(instance, "published_by_id", None) and self.request.user.is_authenticated:
            save_kwargs["published_by"] = self.request.user
        return save_kwargs

    def perform_create(self, serializer):
        with suppress_audit_signals():
            instance = serializer.save(**self._build_save_kwargs(serializer))
        self._create_audit_log("criado", instance, before={}, after=self._serialize_instance_for_log(instance))

    def perform_update(self, serializer):
        before = self._serialize_instance_for_log(serializer.instance)
        with suppress_audit_signals():
            instance = serializer.save(**self._build_save_kwargs(serializer))
        self._create_audit_log("alterado", instance, before=before, after=self._serialize_instance_for_log(instance))

    def perform_destroy(self, instance):
        before = self._serialize_instance_for_log(instance)
        self._create_audit_log("excluido", instance, before=before, after={})

        content_type = ContentType.objects.get_for_model(MarketNewsPost)
        attachments = Attachment.objects.filter(
            tenant=instance.tenant,
            content_type=content_type,
            object_id=instance.pk,
        )

        with suppress_audit_signals():
            for attachment in attachments:
                if getattr(attachment, "file", None):
                    attachment.file.delete(save=False)
            attachments.delete()
            if getattr(instance, "audio", None):
                instance.audio.delete(save=False)
            instance.delete()

    @action(detail=True, methods=["get", "post"], parser_classes=[parsers.MultiPartParser, parsers.FormParser])
    def attachments(self, request, pk=None):
        instance = self.get_object()
        content_type = ContentType.objects.get_for_model(MarketNewsPost)
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
        return Response(
            AttachmentSerializer(created, many=True, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )
