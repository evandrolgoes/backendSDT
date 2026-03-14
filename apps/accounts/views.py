from rest_framework import generics, permissions, response, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.core.permissions import IsMasterAdmin, IsMasterAdminOrTenantUser
from apps.core.viewsets import TenantScopedModelViewSet
from .models import Tenant, User
from .serializers import LoginSerializer, TenantSerializer, UserSerializer


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer

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


class TenantViewSet(TenantScopedModelViewSet):
    queryset = Tenant.objects.all()
    serializer_class = TenantSerializer
    permission_classes = [IsMasterAdmin]


class UserViewSet(TenantScopedModelViewSet):
    queryset = User.objects.select_related("tenant").prefetch_related("user_roles__role").all()
    serializer_class = UserSerializer
    permission_classes = [IsMasterAdminOrTenantUser]
    filterset_fields = ["tenant", "is_active", "is_staff"]
    search_fields = ["username", "email", "full_name"]
    ordering_fields = ["username", "created_at"]
