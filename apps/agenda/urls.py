from django.urls import path

from .views import (
    AgendaEventosView,
    AgendaOAuthCallbackView,
    AgendaOAuthDisconnectView,
    AgendaOAuthInitView,
    ClientAgendaEventAttachmentsView,
    ClientAgendaEventosView,
)

urlpatterns = [
    path("oauth/init/", AgendaOAuthInitView.as_view(), name="agenda_oauth_init"),
    path("oauth/callback/", AgendaOAuthCallbackView.as_view(), name="agenda_oauth_callback"),
    path("oauth/disconnect/<int:pk>/", AgendaOAuthDisconnectView.as_view(), name="agenda_oauth_disconnect"),
    path("eventos/", AgendaEventosView.as_view(), name="agenda_eventos"),
    path("clientes/eventos/", ClientAgendaEventosView.as_view(), name="agenda_clientes_eventos"),
    path("clientes/eventos/<int:pk>/attachments/", ClientAgendaEventAttachmentsView.as_view(), name="agenda_clientes_eventos_attachments"),
]
