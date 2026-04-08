from django.urls import path

from .views import AgendaEventosView, AgendaOAuthCallbackView, AgendaOAuthDisconnectView, AgendaOAuthInitView

urlpatterns = [
    path("oauth/init/", AgendaOAuthInitView.as_view(), name="agenda_oauth_init"),
    path("oauth/callback/", AgendaOAuthCallbackView.as_view(), name="agenda_oauth_callback"),
    path("oauth/disconnect/<int:pk>/", AgendaOAuthDisconnectView.as_view(), name="agenda_oauth_disconnect"),
    path("eventos/", AgendaEventosView.as_view(), name="agenda_eventos"),
]
