from django.db import models
from rest_framework import generics, permissions, response, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.core.permissions import (
    IsMasterAdmin,
    IsMasterAdminOrInvitationTenantAdmin,
    IsMasterAdminOrTenantAdmin,
    IsMasterAdminOrTenantManager,
    IsMasterAdminOrTenantUser,
)
from apps.core.viewsets import TenantScopedModelViewSet
from .models import Invitation, Tenant, User
from .serializers import (
    AccessRequestSerializer,
    AdminInvitationSerializer,
    DashboardFilterSerializer,
    ForgotPasswordSerializer,
    InvitationAcceptSerializer,
    InvitationLookupSerializer,
    InvitationSerializer,
    LoginSerializer,
    ResetPasswordConfirmSerializer,
    TenantSerializer,
    UserSerializer,
)


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer

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
        serializer = DashboardFilterSerializer(request.user.dashboard_filter or {})
        return response.Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, *args, **kwargs):
        serializer = DashboardFilterSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        request.user.dashboard_filter = serializer.validated_data
        request.user.save(update_fields=["dashboard_filter"])
        return response.Response(serializer.validated_data, status=status.HTTP_200_OK)


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


class UserViewSet(TenantScopedModelViewSet):
    queryset = User.objects.select_related("tenant").prefetch_related("assigned_groups", "assigned_subgroups").all()
    serializer_class = UserSerializer
    permission_classes = [IsMasterAdminOrTenantAdmin]
    filterset_fields = ["tenant", "is_active", "role"]
    search_fields = ["username", "email", "full_name"]
    ordering_fields = ["username", "created_at"]

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.user.is_superuser:
            return queryset
        if self.request.user.has_tenant_slug("admin"):
            return queryset
        if self.request.user.has_tenant_slug("consultor"):
            root_user = self.request.user.get_master_root()
            return queryset.filter(models.Q(tenant=self.request.user.tenant) | models.Q(tenant__slug="usuario", master_user=root_user))
        return queryset.filter(tenant=self.request.user.tenant)


class ImpersonateUserView(APIView):
    permission_classes = [IsMasterAdminOrTenantManager]

    def post(self, request, user_id, *args, **kwargs):
        actor = request.user
        target_user = generics.get_object_or_404(User.objects.select_related("tenant"), pk=user_id)

        if not actor.is_superuser:
            accessible_tenant_ids = actor.get_accessible_tenant_ids()
            if not actor.tenant_id or target_user.tenant_id not in accessible_tenant_ids:
                return response.Response({"detail": "Voce so pode acessar usuarios do seu proprio tenant."}, status=status.HTTP_403_FORBIDDEN)
            if target_user.is_superuser:
                return response.Response({"detail": "Nao e permitido impersonar superusuario."}, status=status.HTTP_403_FORBIDDEN)

        refresh = RefreshToken.for_user(target_user)
        user_data = UserSerializer(target_user, context={"request": request}).data
        return response.Response(
            {"access": str(refresh.access_token), "refresh": str(refresh), "user": user_data},
            status=status.HTTP_200_OK,
        )


class InvitationViewSet(TenantScopedModelViewSet):
    queryset = Invitation.objects.select_related("tenant", "invited_by", "accepted_user").all()
    serializer_class = InvitationSerializer
    permission_classes = [IsMasterAdminOrInvitationTenantAdmin]
    filterset_fields = ["tenant", "status"]
    search_fields = ["email"]
    ordering_fields = ["created_at", "expires_at", "status"]

    def get_queryset(self):
        queryset = super().get_queryset().filter(kind=Invitation.Kind.INTERNAL_USER)
        if self.request.user.is_superuser:
            return queryset
        return queryset.filter(tenant=self.request.user.tenant)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["invitation_kind"] = Invitation.Kind.INTERNAL_USER
        return context

    def perform_destroy(self, instance):
        accepted_user = instance.accepted_user
        super().perform_destroy(instance)
        if accepted_user and accepted_user.pk:
            accepted_user.delete()


class AdminInvitationViewSet(TenantScopedModelViewSet):
    queryset = Invitation.objects.select_related("tenant", "invited_by", "accepted_user").all()
    serializer_class = AdminInvitationSerializer
    permission_classes = [IsMasterAdminOrInvitationTenantAdmin]
    filterset_fields = ["tenant", "status"]
    search_fields = ["email", "target_tenant_name", "target_tenant_slug"]
    ordering_fields = ["created_at", "expires_at", "status"]

    def get_queryset(self):
        queryset = super().get_queryset().exclude(kind=Invitation.Kind.INTERNAL_USER)
        if self.request.user.is_superuser:
            return queryset
        return queryset.filter(tenant=self.request.user.tenant)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["invitation_kind"] = Invitation.Kind.PLATFORM_ADMIN
        return context

    def perform_destroy(self, instance):
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
