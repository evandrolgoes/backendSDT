from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from apps.anotacoes.views import AnotacaoViewSet, anotacoes_health
from apps.accounts.views import (
    AccessRequestView,
    AdminInvitationViewSet,
    DashboardFilterView,
    ForgotPasswordView,
    InvitationAcceptView,
    InvitationDetailByTokenView,
    InvitationViewSet,
    ImpersonateUserView,
    LoginView,
    ResetPasswordConfirmView,
    TenantViewSet,
    UserViewSet,
    me,
)
from apps.auditing.views import AttachmentViewSet, AuditLogViewSet
from apps.catalog.views import CropViewSet, CurrencyViewSet, DerivativeOperationNameViewSet, ExchangeViewSet, MarketInstrumentViewSet, PriceSourceViewSet, PriceUnitViewSet, UnitViewSet
from apps.clients.views import BrokerViewSet, ClientAccountViewSet, CounterpartyViewSet, CropSeasonViewSet, EconomicGroupViewSet, SubGroupViewSet
from apps.derivatives.views import (
    DerivativeOperationViewSet,
    derivative_contracts,
    import_bubble_targets,
    import_bubble_derivatives,
    inspect_bubble_import,
)
from apps.marketdata.views import BasisSeriesViewSet, FxRateViewSet, MarketPriceViewSet
from apps.mass_update.views import (
    MassImportApplyView,
    MassImportMetadataView,
    MassImportResourcesView,
    MassUpdateApplyView,
    MassUpdateMetadataView,
    MassUpdatePreviewView,
    MassUpdateResourcesView,
)
from apps.mass_update.copy_base_views import CopyBaseApplyView, CopyBasePreviewView, CopyBaseTargetsView
from apps.mercado.views import MarketNewsPostViewSet, mercado_health
from apps.payables.views import AccountsPayableViewSet
from apps.leads.views import LeadCreateView
from apps.physical.views import (
    ActualCostViewSet,
    BudgetCostViewSet,
    CashPaymentViewSet,
    PhysicalPaymentViewSet,
    PhysicalQuoteViewSet,
    PhysicalSaleViewSet,
)
from apps.receivables.views import ReceiptEntryViewSet
from apps.risk.views import ExposurePositionViewSet
from apps.strategies.views import CropBoardViewSet, HedgePolicyViewSet, StrategyTriggerViewSet, StrategyViewSet, ibge_cities, ibge_states
from apps.tradingview_scraper.views import TradingViewWatchlistQuoteViewSet

router = DefaultRouter()
router.register("tenants", TenantViewSet, basename="tenant")
router.register("users", UserViewSet, basename="user")
router.register("invitations", InvitationViewSet, basename="invitation")
router.register("admin-invitations", AdminInvitationViewSet, basename="admin-invitation")
router.register("clients", ClientAccountViewSet, basename="client")
router.register("groups", EconomicGroupViewSet, basename="group")
router.register("subgroups", SubGroupViewSet, basename="subgroup")
router.register("crops", CropViewSet, basename="crop")
router.register("currencies", CurrencyViewSet, basename="currency")
router.register("units", UnitViewSet, basename="unit")
router.register("price-units", PriceUnitViewSet, basename="price-unit")
router.register("exchanges", ExchangeViewSet, basename="exchange")
router.register("derivative-operation-names", DerivativeOperationNameViewSet, basename="derivative-operation-name")
router.register("seasons", CropSeasonViewSet, basename="season")
router.register("counterparties", CounterpartyViewSet, basename="counterparty")
router.register("brokers", BrokerViewSet, basename="broker")
router.register("instruments", MarketInstrumentViewSet, basename="instrument")
router.register("price-sources", PriceSourceViewSet, basename="price-source")
router.register("physical-quotes", PhysicalQuoteViewSet, basename="physical-quote")
router.register("budget-costs", BudgetCostViewSet, basename="budget-cost")
router.register("actual-costs", ActualCostViewSet, basename="actual-cost")
router.register("physical-sales", PhysicalSaleViewSet, basename="physical-sale")
router.register("physical-payments", PhysicalPaymentViewSet, basename="physical-payment")
router.register("cash-payments", CashPaymentViewSet, basename="cash-payment")
router.register("receipt-entries", ReceiptEntryViewSet, basename="receipt-entry")
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
router.register("tradingview-watchlist-quotes", TradingViewWatchlistQuoteViewSet, basename="tradingview-watchlist-quote")
router.register("market-news-posts", MarketNewsPostViewSet, basename="market-news-post")
router.register("anotacoes", AnotacaoViewSet, basename="anotacao")
router.register("accounts-payable", AccountsPayableViewSet, basename="accounts-payable")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(router.urls)),
    path("api/health/", lambda request: JsonResponse({"status": "ok"}), name="health"),
    path("api/mercado/health/", mercado_health, name="mercado_health"),
    path("api/anotacoes/health/", anotacoes_health, name="anotacoes_health"),
    path("api/derivative-contracts/", derivative_contracts, name="derivative_contracts"),
    path("api/import-tools/bubble/targets/", import_bubble_targets, name="import_bubble_targets"),
    path("api/import-tools/bubble/inspect/", inspect_bubble_import, name="inspect_bubble_import"),
    path("api/import-tools/bubble/derivatives/", import_bubble_derivatives, name="import_bubble_derivatives"),
    path("api/copy-base/targets/", CopyBaseTargetsView.as_view(), name="copy_base_targets"),
    path("api/copy-base/preview/", CopyBasePreviewView.as_view(), name="copy_base_preview"),
    path("api/copy-base/apply/", CopyBaseApplyView.as_view(), name="copy_base_apply"),
    path("api/mass-update/resources/", MassUpdateResourcesView.as_view(), name="mass_update_resources"),
    path("api/mass-update/metadata/", MassUpdateMetadataView.as_view(), name="mass_update_metadata"),
    path("api/mass-update/preview/", MassUpdatePreviewView.as_view(), name="mass_update_preview"),
    path("api/mass-update/apply/", MassUpdateApplyView.as_view(), name="mass_update_apply"),
    path("api/mass-import/resources/", MassImportResourcesView.as_view(), name="mass_import_resources"),
    path("api/mass-import/metadata/", MassImportMetadataView.as_view(), name="mass_import_metadata"),
    path("api/mass-import/apply/", MassImportApplyView.as_view(), name="mass_import_apply"),
    path("api/localidades/estados/", ibge_states, name="ibge_states"),
    path("api/localidades/municipios/", ibge_cities, name="ibge_cities"),
    path("api/auth/login/", LoginView.as_view(), name="login"),
    path("api/auth/impersonate/<int:user_id>/", ImpersonateUserView.as_view(), name="impersonate_user"),
    path("api/auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/auth/me/", me, name="me"),
    path("api/auth/dashboard-filter/", DashboardFilterView.as_view(), name="dashboard_filter"),
    path("api/auth/forgot-password/", ForgotPasswordView.as_view(), name="forgot_password"),
    path("api/auth/reset-password-confirm/", ResetPasswordConfirmView.as_view(), name="reset_password_confirm"),
    path("api/auth/request-access/", AccessRequestView.as_view(), name="request_access"),
    path("api/auth/invitations/<str:token>/", InvitationDetailByTokenView.as_view(), name="invitation_detail_by_token"),
    path("api/auth/invitations/<str:token>/accept/", InvitationAcceptView.as_view(), name="invitation_accept"),
    path("api/leads/", LeadCreateView.as_view(), name="lead_create"),
]

if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
