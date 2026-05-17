from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from .models import GamingSession
from .serializers import GamingSessionSerializer


class GamingSessionViewSet(ModelViewSet):
    queryset = GamingSession.objects.all()
    serializer_class = GamingSessionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["game_code", "kind"]
    ordering_fields = ["final_price", "ts", "created_at"]
    ordering = ["-final_price"]

    def get_queryset(self):
        # Sessoes de usuario teste nunca entram no ranking/lista.
        return super().get_queryset().exclude(is_test=True)

    def perform_create(self, serializer):
        user = self.request.user
        is_test = bool(getattr(user, "is_authenticated", False) and user.is_test_account())
        serializer.save(is_test=is_test)
