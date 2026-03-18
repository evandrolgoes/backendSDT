from rest_framework import generics, permissions, response, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.core.permissions import IsMasterAdmin, IsMasterAdminOrTenantUser
from apps.core.viewsets import TenantScopedModelViewSet
from .models import Tenant, User
from .serializers import (
    AccessRequestSerializer,
    ForgotPasswordSerializer,
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
    queryset = User.objects.select_related("tenant").prefetch_related("user_roles__role", "assigned_groups", "assigned_subgroups").all()
    serializer_class = UserSerializer
    permission_classes = [IsMasterAdminOrTenantUser]
    filterset_fields = ["tenant", "is_active", "is_staff"]
    search_fields = ["username", "email", "full_name"]
    ordering_fields = ["username", "created_at"]
