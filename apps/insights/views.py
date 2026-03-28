from rest_framework import permissions, response
from rest_framework.views import APIView

from .services import build_insights_payload


class CommercialInsightsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        payload = build_insights_payload(request)
        return response.Response(payload)
