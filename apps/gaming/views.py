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
