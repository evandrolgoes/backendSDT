from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from apps.accounts.views import LoginView, TenantViewSet, UserViewSet, me
from apps.auditing.views import AttachmentViewSet, AuditLogViewSet
from apps.catalog.views import CropViewSet, MarketInstrumentViewSet, PriceSourceViewSet, UnitOfMeasureViewSet
from apps.clients.views import BrokerViewSet, ClientAccountViewSet, CounterpartyViewSet, CropSeasonViewSet, EconomicGroupViewSet, SubGroupViewSet
from apps.derivatives.views import CashSettlementViewSet, DerivativeLegViewSet, DerivativeOperationViewSet, MarkToMarketSnapshotViewSet
from apps.marketdata.views import BasisSeriesViewSet, FxRateViewSet, MarketPriceViewSet
from apps.physical.views import HedgeAllocationViewSet, PhysicalSaleViewSet
from apps.risk.views import ExposurePositionViewSet
from apps.strategies.views import StrategyTriggerViewSet, StrategyViewSet, TriggerEventViewSet

router = DefaultRouter()
router.register("tenants", TenantViewSet, basename="tenant")
router.register("users", UserViewSet, basename="user")
router.register("clients", ClientAccountViewSet, basename="client")
router.register("groups", EconomicGroupViewSet, basename="group")
router.register("subgroups", SubGroupViewSet, basename="subgroup")
router.register("crops", CropViewSet, basename="crop")
router.register("seasons", CropSeasonViewSet, basename="season")
router.register("counterparties", CounterpartyViewSet, basename="counterparty")
router.register("brokers", BrokerViewSet, basename="broker")
router.register("units", UnitOfMeasureViewSet, basename="unit")
router.register("instruments", MarketInstrumentViewSet, basename="instrument")
router.register("price-sources", PriceSourceViewSet, basename="price-source")
router.register("physical-sales", PhysicalSaleViewSet, basename="physical-sale")
router.register("derivative-operations", DerivativeOperationViewSet, basename="derivative-operation")
router.register("derivative-legs", DerivativeLegViewSet, basename="derivative-leg")
router.register("hedge-allocations", HedgeAllocationViewSet, basename="hedge-allocation")
router.register("strategies", StrategyViewSet, basename="strategy")
router.register("strategy-triggers", StrategyTriggerViewSet, basename="strategy-trigger")
router.register("trigger-events", TriggerEventViewSet, basename="trigger-event")
router.register("market-prices", MarketPriceViewSet, basename="market-price")
router.register("fx-rates", FxRateViewSet, basename="fx-rate")
router.register("basis-series", BasisSeriesViewSet, basename="basis-series")
router.register("mtm-snapshots", MarkToMarketSnapshotViewSet, basename="mtm-snapshot")
router.register("cash-settlements", CashSettlementViewSet, basename="cash-settlement")
router.register("exposure-positions", ExposurePositionViewSet, basename="exposure-position")
router.register("audit-logs", AuditLogViewSet, basename="audit-log")
router.register("attachments", AttachmentViewSet, basename="attachment")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(router.urls)),
    path("api/health/", lambda request: JsonResponse({"status": "ok"}), name="health"),
    path("api/auth/login/", LoginView.as_view(), name="login"),
    path("api/auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/auth/me/", me, name="me"),
]
