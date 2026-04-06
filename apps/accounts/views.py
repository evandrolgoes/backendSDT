from rest_framework import generics, permissions, response, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import MethodNotAllowed, PermissionDenied
from rest_framework.throttling import AnonRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView


class LoginRateThrottle(AnonRateThrottle):
    scope = "login"

from apps.core.permissions import (
    IsMasterAdmin,
    IsMasterAdminOrInvitationTenantAdmin,
    IsMasterAdminOrTenantAdmin,
    IsMasterAdminOrTenantManager,
    IsMasterAdminOrTenantUser,
)
from apps.core.privacy import sanitize_dashboard_filter
from apps.core.viewsets import TenantScopedModelViewSet
from .constants import AVAILABLE_MODULES
from .models import Invitation, Tenant, User
from .serializers import (
    AccessRequestSerializer,
    AdminInvitationSerializer,
    DashboardFilterSerializer,
    ForgotPasswordSerializer,
    InvitationAcceptSerializer,
    InvitationLookupSerializer,
    LoginSerializer,
    ResetPasswordConfirmSerializer,
    TenantSerializer,
    UserSerializer,
)


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer
    throttle_classes = [LoginRateThrottle]

    def get(self, request, *args, **kwargs):
        return response.Response(
            {"detail": 'Use POST para autenticar com "username" e "password".'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_data = UserSerializer(serializer.validated_data["user"], context={"request": request}).data
        return response.Response(
            {"access": serializer.validated_data["access"], "refresh": serializer.validated_data["refresh"], "user": user_data},
            status=status.HTTP_200_OK,
        )


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def me(request):
    return response.Response(UserSerializer(request.user, context={"request": request}).data)


class DashboardFilterView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        serializer = DashboardFilterSerializer(sanitize_dashboard_filter(request.user, request.user.dashboard_filter or {}))
        return response.Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, *args, **kwargs):
        serializer = DashboardFilterSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        request.user.dashboard_filter = sanitize_dashboard_filter(request.user, serializer.validated_data)
        request.user.save(update_fields=["dashboard_filter"])
        return response.Response(request.user.dashboard_filter, status=status.HTTP_200_OK)


class ForgotPasswordView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return response.Response(
            {"detail": "Se o e-mail informado estiver cadastrado, voce recebera um link para redefinicao de senha."},
            status=status.HTTP_200_OK,
        )


class ResetPasswordConfirmView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = ResetPasswordConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return response.Response({"detail": "Senha redefinida com sucesso."}, status=status.HTTP_200_OK)


class AccessRequestView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = AccessRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return response.Response(
            {"detail": "Solicitacao enviada com sucesso. Em breve entraremos em contato."},
            status=status.HTTP_200_OK,
        )


class TenantViewSet(TenantScopedModelViewSet):
    queryset = Tenant.objects.all()
    serializer_class = TenantSerializer
    permission_classes = [IsMasterAdmin]

    @action(detail=False, methods=["get"], url_path="available-modules")
    def available_modules(self, request, *args, **kwargs):
        labels_by_code = {code: label for code, label in AVAILABLE_MODULES}
        configured_codes = []
        for tenant in Tenant.objects.only("enabled_modules"):
            for code in tenant.enabled_modules or []:
                normalized = str(code or "").strip()
                if normalized and normalized not in configured_codes:
                    configured_codes.append(normalized)
        all_codes = list(labels_by_code.keys()) + [code for code in configured_codes if code not in labels_by_code]
        modules = [{"id": code, "value": code, "label": labels_by_code.get(code, code), "name": labels_by_code.get(code, code)} for code in all_codes]
        return response.Response(modules, status=status.HTTP_200_OK)


class UserViewSet(TenantScopedModelViewSet):
    queryset = User.objects.select_related("tenant", "master_user").prefetch_related("accessible_groups", "accessible_subgroups").all()
    serializer_class = UserSerializer
    permission_classes = [IsMasterAdminOrTenantAdmin]
    filterset_fields = ["is_active", "role"]
    search_fields = ["username", "email", "full_name"]
    ordering_fields = ["username", "created_at"]

    def get_queryset(self):
        return self.queryset

class ImpersonateUserView(APIView):
    permission_classes = [IsMasterAdminOrTenantManager]

    def post(self, request, user_id, *args, **kwargs):
        actor = request.user
        target_user = generics.get_object_or_404(User.objects.select_related("tenant"), pk=user_id)

        if not actor.is_superuser and target_user.is_superuser:
            return response.Response({"detail": "Nao e permitido impersonar superusuario."}, status=status.HTTP_403_FORBIDDEN)

        refresh = RefreshToken.for_user(target_user)
        user_data = UserSerializer(target_user, context={"request": request}).data
        return response.Response(
            {"access": str(refresh.access_token), "refresh": str(refresh), "user": user_data},
            status=status.HTTP_200_OK,
        )


class AdminInvitationViewSet(TenantScopedModelViewSet):
    queryset = Invitation.objects.select_related("tenant", "invited_by", "accepted_user").all()
    serializer_class = AdminInvitationSerializer
    permission_classes = [IsMasterAdminOrInvitationTenantAdmin]
    filterset_fields = ["status"]
    search_fields = ["email", "target_tenant_name", "target_tenant_slug"]
    ordering_fields = ["created_at", "expires_at", "status"]

    def get_queryset(self):
        return super().get_queryset().filter(kind=Invitation.Kind.PLATFORM_ADMIN)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["invitation_kind"] = Invitation.Kind.PLATFORM_ADMIN
        return context

    def update(self, request, *args, **kwargs):
        raise MethodNotAllowed("PUT", detail="Convites enviados nao podem ser editados.")

    def partial_update(self, request, *args, **kwargs):
        raise MethodNotAllowed("PATCH", detail="Convites enviados nao podem ser editados.")

    def perform_destroy(self, instance):
        if not self.request.user.is_superuser:
            raise PermissionDenied("Apenas superusuario pode excluir convites.")
        accepted_user = instance.accepted_user
        super().perform_destroy(instance)
        if accepted_user and accepted_user.pk:
            accepted_user.delete()


class InvitationDetailByTokenView(APIView):
    permission_classes = [permissions.AllowAny]

    def get_object(self, token):
        return generics.get_object_or_404(Invitation.objects.select_related("tenant"), token=token)

    def get(self, request, token, *args, **kwargs):
        invitation = self.get_object(token)
        serializer = InvitationLookupSerializer(invitation)
        return response.Response(serializer.data, status=status.HTTP_200_OK)


class InvitationAcceptView(APIView):
    permission_classes = [permissions.AllowAny]

    def get_object(self, token):
        return generics.get_object_or_404(Invitation.objects.select_related("tenant"), token=token)

    def post(self, request, token, *args, **kwargs):
        invitation = self.get_object(token)
        serializer = InvitationAcceptSerializer(data=request.data, context={"invitation": invitation})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return response.Response({"detail": "Conta criada com sucesso. Agora voce ja pode entrar no sistema."}, status=status.HTTP_201_CREATED)
