from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from apps.accounts.views import LoginView, TenantViewSet, UserViewSet, me
from apps.auditing.views import AttachmentViewSet, AuditLogViewSet
from apps.catalog.views import CropViewSet, CurrencyViewSet, ExchangeViewSet, MarketInstrumentViewSet, PriceSourceViewSet, PriceUnitViewSet, UnitViewSet
from apps.clients.views import BrokerViewSet, ClientAccountViewSet, CounterpartyViewSet, CropSeasonViewSet, EconomicGroupViewSet, SubGroupViewSet
from apps.derivatives.views import DerivativeOperationViewSet
from apps.marketdata.views import BasisSeriesViewSet, FxRateViewSet, MarketPriceViewSet
from apps.physical.views import ActualCostViewSet, BudgetCostViewSet, PhysicalQuoteViewSet, PhysicalSaleViewSet
from apps.risk.views import ExposurePositionViewSet
from apps.strategies.views import CropBoardViewSet, HedgePolicyViewSet, StrategyTriggerViewSet, StrategyViewSet

router = DefaultRouter()
router.register("tenants", TenantViewSet, basename="tenant")
router.register("users", UserViewSet, basename="user")
router.register("clients", ClientAccountViewSet, basename="client")
router.register("groups", EconomicGroupViewSet, basename="group")
router.register("subgroups", SubGroupViewSet, basename="subgroup")
router.register("crops", CropViewSet, basename="crop")
router.register("currencies", CurrencyViewSet, basename="currency")
router.register("units", UnitViewSet, basename="unit")
router.register("price-units", PriceUnitViewSet, basename="price-unit")
router.register("exchanges", ExchangeViewSet, basename="exchange")
router.register("seasons", CropSeasonViewSet, basename="season")
router.register("counterparties", CounterpartyViewSet, basename="counterparty")
router.register("brokers", BrokerViewSet, basename="broker")
router.register("instruments", MarketInstrumentViewSet, basename="instrument")
router.register("price-sources", PriceSourceViewSet, basename="price-source")
router.register("physical-quotes", PhysicalQuoteViewSet, basename="physical-quote")
router.register("budget-costs", BudgetCostViewSet, basename="budget-cost")
router.register("actual-costs", ActualCostViewSet, basename="actual-cost")
router.register("physical-sales", PhysicalSaleViewSet, basename="physical-sale")
router.register("derivative-operations", DerivativeOperationViewSet, basename="derivative-operation")
router.register("strategies", StrategyViewSet, basename="strategy")
router.register("strategy-triggers", StrategyTriggerViewSet, basename="strategy-trigger")
router.register("hedge-policies", HedgePolicyViewSet, basename="hedge-policy")
router.register("crop-boards", CropBoardViewSet, basename="crop-board")
router.register("market-prices", MarketPriceViewSet, basename="market-price")
router.register("fx-rates", FxRateViewSet, basename="fx-rate")
router.register("basis-series", BasisSeriesViewSet, basename="basis-series")
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
