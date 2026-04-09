from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core import signing
from django.shortcuts import redirect
from rest_framework import parsers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from apps.auditing.models import Attachment
from apps.auditing.serializers import AttachmentSerializer
from apps.core.viewsets import TenantScopedModelViewSet

from .models import ClientAgendaEvent, GoogleCalendarConfig
from .serializers import ClientAgendaEventSerializer, GoogleCalendarConfigSerializer

GOOGLE_CALENDAR_SCOPES = [
    "https://www.googleapis.com/auth/calendar",
]

_SIGNING_SALT = "agenda_oauth_state"
_STATE_MAX_AGE = 600  # 10 minutos


def _build_recurrence_rule(repeticao, repetir_ate):
    repeat_mode = str(repeticao or "").strip().lower()
    until_value = str(repetir_ate or "").strip()
    if repeat_mode not in {"weekly", "monthly"} or not until_value:
        return None

    try:
        until_date = datetime.strptime(until_value, "%Y-%m-%d")
    except ValueError:
        return None

    freq = "WEEKLY" if repeat_mode == "weekly" else "MONTHLY"
    until_formatted = until_date.strftime("%Y%m%dT235959Z")
    return f"RRULE:FREQ={freq};UNTIL={until_formatted}"


def _shift_month(date_value):
    month = date_value.month - 1 + 1
    year = date_value.year + month // 12
    month = month % 12 + 1
    from calendar import monthrange
    day = min(date_value.day, monthrange(year, month)[1])
    return date_value.replace(year=year, month=month, day=day)


def _iter_client_event_occurrences(event, range_start, range_end):
    occurrence_date = event.data_inicio
    limit_date = event.repetir_ate or event.data_fim or event.data_inicio
    duration_days = max((event.data_fim - event.data_inicio).days, 0)

    while occurrence_date <= range_end and occurrence_date <= limit_date:
        occurrence_end = occurrence_date + timedelta(days=duration_days)
        if occurrence_date <= range_end and occurrence_end >= range_start:
            yield occurrence_date, occurrence_end

        if event.repeticao == ClientAgendaEvent.RepeatChoices.WEEKLY:
            occurrence_date = occurrence_date + timedelta(days=7)
        elif event.repeticao == ClientAgendaEvent.RepeatChoices.MONTHLY:
            occurrence_date = _shift_month(occurrence_date)
        else:
            break


def _serialize_client_event(event, occurrence_start, occurrence_end):
    if event.dia_todo:
        start_payload = {"date": occurrence_start.isoformat()}
        end_payload = {"date": occurrence_end.isoformat()}
    else:
        start_dt = datetime.combine(occurrence_start, event.hora_inicio or datetime.min.time())
        end_dt = datetime.combine(occurrence_end, event.hora_fim or event.hora_inicio or datetime.min.time())
        start_payload = {"dateTime": start_dt.isoformat(), "timeZone": "America/Sao_Paulo"}
        end_payload = {"dateTime": end_dt.isoformat(), "timeZone": "America/Sao_Paulo"}

    recurrence = []
    recurrence_rule = _build_recurrence_rule(event.repeticao, event.repetir_ate.isoformat() if event.repetir_ate else "")
    if recurrence_rule:
        recurrence = [recurrence_rule]

    return {
        "id": str(event.id),
        "recurringEventId": str(event.id) if recurrence else "",
        "summary": event.titulo,
        "description": event.descricao,
        "location": event.local,
        "participantes": event.participantes,
        "created_at": event.created_at.isoformat() if event.created_at else "",
        "updated_at": event.updated_at.isoformat() if event.updated_at else "",
        "start": start_payload,
        "end": end_payload,
        "recurrence": recurrence,
        "grupo_ids": list(event.grupos.order_by("grupo", "id").values_list("id", flat=True)),
        "subgrupo_ids": list(event.subgrupos.order_by("subgrupo", "id").values_list("id", flat=True)),
        "grupos_display": list(event.grupos.order_by("grupo", "id").values_list("grupo", flat=True)),
        "subgrupos_display": list(event.subgrupos.order_by("subgrupo", "id").values_list("subgrupo", flat=True)),
    }


def _get_redirect_uri(request):
    redirect_uri = getattr(settings, "GOOGLE_CALENDAR_REDIRECT_URI", None)
    if redirect_uri:
        return redirect_uri
    scheme = "https" if not settings.DEBUG else "http"
    host = request.get_host()
    return f"{scheme}://{host}/api/agenda/oauth/callback/"


def _build_flow(config, redirect_uri):
    try:
        from google_auth_oauthlib.flow import Flow
    except ImportError:
        raise ImportError(
            "google-auth-oauthlib nao esta instalado. "
            "Execute: pip install google-auth-oauthlib google-api-python-client"
        )

    client_config = {
        "web": {
            "client_id": config.client_id,
            "client_secret": config.client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    flow = Flow.from_client_config(client_config, scopes=GOOGLE_CALENDAR_SCOPES)
    flow.redirect_uri = redirect_uri
    return flow


class GoogleCalendarConfigViewSet(TenantScopedModelViewSet):
    queryset = GoogleCalendarConfig.objects.select_related("tenant").all()
    serializer_class = GoogleCalendarConfigSerializer

    def perform_destroy(self, instance):
        instance.delete()


class AgendaOAuthInitView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        config_id = request.query_params.get("config_id")
        if not config_id:
            return Response({"detail": "config_id e obrigatorio."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            config = GoogleCalendarConfig.objects.get(id=config_id, tenant=request.user.tenant)
        except GoogleCalendarConfig.DoesNotExist:
            return Response({"detail": "Configuracao nao encontrada."}, status=status.HTTP_404_NOT_FOUND)

        redirect_uri = _get_redirect_uri(request)
        try:
            flow = _build_flow(config, redirect_uri)
        except ImportError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        auth_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
        )

        state_payload = {
            "config_id": config.pk,
            "tenant_id": request.user.tenant.pk,
            "code_verifier": getattr(flow, "code_verifier", None) or "",
        }
        signed_state = signing.dumps(state_payload, salt=_SIGNING_SALT)

        # Substitui o state gerado pelo google pelo nosso state assinado
        from urllib.parse import urlencode, urlparse, parse_qs, urlunparse
        parsed = urlparse(auth_url)
        params = parse_qs(parsed.query, keep_blank_values=True)
        params["state"] = [signed_state]
        new_query = urlencode({k: v[0] for k, v in params.items()})
        auth_url = urlunparse(parsed._replace(query=new_query))

        return Response({"auth_url": auth_url})


class AgendaOAuthCallbackView(APIView):
    permission_classes = []
    authentication_classes = []

    def get(self, request):
        import logging
        logger = logging.getLogger("agenda.oauth")

        code = request.query_params.get("code")
        signed_state = request.query_params.get("state")
        error = request.query_params.get("error")

        frontend_base = getattr(settings, "GOOGLE_CALENDAR_FRONTEND_URL", "")
        success_url = f"{frontend_base}/agenda-config?oauth=success"
        error_url = f"{frontend_base}/agenda-config?oauth=error"

        logger.warning(f"[AGENDA OAUTH] code={'ok' if code else 'MISSING'} state={'ok' if signed_state else 'MISSING'} error={error}")

        if error or not code or not signed_state:
            logger.warning(f"[AGENDA OAUTH] Abortando: error={error} code={bool(code)} state={bool(signed_state)}")
            return redirect(error_url)

        try:
            state_payload = signing.loads(signed_state, salt=_SIGNING_SALT, max_age=_STATE_MAX_AGE)
            config_id = state_payload["config_id"]
            tenant_id = state_payload["tenant_id"]
            code_verifier = state_payload.get("code_verifier") or None
        except signing.BadSignature as exc:
            logger.warning(f"[AGENDA OAUTH] BadSignature: {exc}")
            return redirect(error_url)

        try:
            config = GoogleCalendarConfig.objects.get(id=config_id, tenant_id=tenant_id)
        except GoogleCalendarConfig.DoesNotExist:
            logger.warning(f"[AGENDA OAUTH] Config nao encontrada: config_id={config_id} tenant_id={tenant_id}")
            return redirect(error_url)

        redirect_uri = _get_redirect_uri(request)
        logger.warning(f"[AGENDA OAUTH] redirect_uri={redirect_uri}")
        try:
            flow = _build_flow(config, redirect_uri)
        except ImportError as exc:
            logger.warning(f"[AGENDA OAUTH] ImportError: {exc}")
            return redirect(error_url)

        try:
            fetch_kwargs = {"code": code}
            if code_verifier:
                fetch_kwargs["code_verifier"] = code_verifier
            flow.fetch_token(**fetch_kwargs)
            credentials = flow.credentials
        except Exception as exc:
            logger.warning(f"[AGENDA OAUTH] fetch_token falhou: {exc}")
            return redirect(error_url)

        refresh_token = credentials.refresh_token
        if refresh_token:
            config.refresh_token = refresh_token
            config.conectada = True
            config.save(update_fields=["refresh_token", "conectada", "updated_at"])

        return redirect(success_url)


class AgendaOAuthDisconnectView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk=None):
        try:
            config = GoogleCalendarConfig.objects.get(id=pk, tenant=request.user.tenant)
        except GoogleCalendarConfig.DoesNotExist:
            return Response({"detail": "Configuracao nao encontrada."}, status=status.HTTP_404_NOT_FOUND)

        config.refresh_token = ""
        config.conectada = False
        config.save(update_fields=["refresh_token", "conectada", "updated_at"])
        return Response({"detail": "Agenda desconectada."})


def _get_calendar_service(config):
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    credentials = Credentials(
        token=None,
        refresh_token=config.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=config.client_id,
        client_secret=config.client_secret,
        scopes=GOOGLE_CALENDAR_SCOPES,
    )
    return build("calendar", "v3", credentials=credentials)


def _get_config_or_error(config_id, tenant):
    try:
        config = GoogleCalendarConfig.objects.get(id=config_id, tenant=tenant)
    except GoogleCalendarConfig.DoesNotExist:
        return None, Response({"detail": "Configuracao nao encontrada."}, status=status.HTTP_404_NOT_FOUND)
    if not config.conectada or not config.refresh_token:
        return None, Response(
            {"detail": "Agenda nao conectada. Conecte a agenda pelo painel de configuracao."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return config, None


class AgendaEventosView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        config_id = request.query_params.get("config_id")
        data_inicio = request.query_params.get("data_inicio")
        data_fim = request.query_params.get("data_fim")

        if not config_id:
            return Response({"detail": "config_id e obrigatorio."}, status=status.HTTP_400_BAD_REQUEST)

        config, err = _get_config_or_error(config_id, request.user.tenant)
        if err:
            return err

        try:
            service = _get_calendar_service(config)
            kwargs = {
                "calendarId": config.calendar_id,
                "singleEvents": True,
                "orderBy": "startTime",
                "maxResults": 250,
            }
            if data_inicio:
                kwargs["timeMin"] = data_inicio if "T" in data_inicio else f"{data_inicio}T00:00:00Z"
            if data_fim:
                kwargs["timeMax"] = data_fim if "T" in data_fim else f"{data_fim}T23:59:59Z"

            events_result = service.events().list(**kwargs).execute()
            events = events_result.get("items", [])
        except Exception as exc:
            return Response({"detail": f"Erro ao buscar eventos: {exc}"}, status=status.HTTP_502_BAD_GATEWAY)

        return Response({"eventos": events, "config_nome": config.nome})

    def post(self, request):
        return self._save_event(request, event_id=None)

    def put(self, request):
        event_id = request.data.get("event_id")
        if not event_id:
            return Response({"detail": "event_id e obrigatorio para edicao."}, status=status.HTTP_400_BAD_REQUEST)
        return self._save_event(request, event_id=event_id)

    def _save_event(self, request, event_id=None):
        config_id = request.data.get("config_id")
        if not config_id:
            return Response({"detail": "config_id e obrigatorio."}, status=status.HTTP_400_BAD_REQUEST)

        config, err = _get_config_or_error(config_id, request.user.tenant)
        if err:
            return err

        titulo = str(request.data.get("titulo") or "").strip()
        data_inicio = str(request.data.get("data_inicio") or "").strip()
        data_fim = str(request.data.get("data_fim") or "").strip()
        hora_inicio = str(request.data.get("hora_inicio") or "").strip()
        hora_fim = str(request.data.get("hora_fim") or "").strip()
        descricao = str(request.data.get("descricao") or "").strip()
        local = str(request.data.get("local") or "").strip()
        dia_todo = bool(request.data.get("dia_todo", False))
        com_meet = bool(request.data.get("com_meet", False))
        convidados = request.data.get("convidados") or []
        enviar_convites = bool(request.data.get("enviar_convites", False))
        repeticao = str(request.data.get("repeticao") or "").strip().lower()
        repetir_ate = str(request.data.get("repetir_ate") or "").strip()
        if not titulo:
            return Response({"detail": "Titulo e obrigatorio."}, status=status.HTTP_400_BAD_REQUEST)
        if not data_inicio:
            return Response({"detail": "Data de inicio e obrigatoria."}, status=status.HTTP_400_BAD_REQUEST)
        if repeticao in {"weekly", "monthly"} and not repetir_ate:
            return Response({"detail": "Informe a data final da repeticao."}, status=status.HTTP_400_BAD_REQUEST)

        if dia_todo:
            event_body = {
                "summary": titulo,
                "start": {"date": data_inicio},
                "end": {"date": data_fim or data_inicio},
            }
        else:
            inicio_dt = f"{data_inicio}T{hora_inicio or '09:00'}:00"
            fim_dt = f"{(data_fim or data_inicio)}T{hora_fim or '10:00'}:00"
            event_body = {
                "summary": titulo,
                "start": {"dateTime": inicio_dt, "timeZone": "America/Sao_Paulo"},
                "end": {"dateTime": fim_dt, "timeZone": "America/Sao_Paulo"},
            }

        if descricao:
            event_body["description"] = descricao
        if local:
            event_body["location"] = local

        # Google Meet
        if com_meet:
            import uuid
            event_body["conferenceData"] = {
                "createRequest": {
                    "requestId": str(uuid.uuid4()),
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                }
            }

        # Convidados
        if isinstance(convidados, list) and convidados:
            event_body["attendees"] = [{"email": e.strip()} for e in convidados if str(e).strip()]

        recurrence_rule = _build_recurrence_rule(repeticao, repetir_ate)
        if recurrence_rule:
            event_body["recurrence"] = [recurrence_rule]

        try:
            service = _get_calendar_service(config)
            send_updates = "all" if enviar_convites else "none"
            conference_version = 1 if com_meet else 0

            if event_id:
                evento = service.events().update(
                    calendarId=config.calendar_id,
                    eventId=event_id,
                    body=event_body,
                    sendUpdates=send_updates,
                    conferenceDataVersion=conference_version,
                ).execute()
            else:
                evento = service.events().insert(
                    calendarId=config.calendar_id,
                    body=event_body,
                    sendUpdates=send_updates,
                    conferenceDataVersion=conference_version,
                ).execute()
        except Exception as exc:
            return Response({"detail": f"Erro ao salvar evento: {exc}"}, status=status.HTTP_502_BAD_GATEWAY)

        code = status.HTTP_200_OK if event_id else status.HTTP_201_CREATED
        return Response({"evento": evento}, status=code)


class ClientAgendaEventosView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data_inicio = str(request.query_params.get("data_inicio") or "").strip()
        data_fim = str(request.query_params.get("data_fim") or "").strip()

        queryset = (
            ClientAgendaEvent.objects.filter(tenant=request.user.tenant)
            .prefetch_related("grupos", "subgrupos")
            .order_by("data_inicio", "hora_inicio", "id")
        )

        if data_inicio or data_fim:
            if not data_inicio or not data_fim:
                return Response({"detail": "Informe data_inicio e data_fim juntos, ou omita ambos."}, status=status.HTTP_400_BAD_REQUEST)
            try:
                range_start = datetime.strptime(data_inicio[:10], "%Y-%m-%d").date()
                range_end = datetime.strptime(data_fim[:10], "%Y-%m-%d").date()
            except ValueError:
                return Response({"detail": "Formato de data invalido."}, status=status.HTTP_400_BAD_REQUEST)
        else:
            items = list(queryset)
            if not items:
                return Response({"eventos": []})
            range_start = min(item.data_inicio for item in items)
            range_end = max((item.repetir_ate or item.data_fim or item.data_inicio) for item in items)
            queryset = items

        eventos = []
        for item in queryset:
            for occurrence_start, occurrence_end in _iter_client_event_occurrences(item, range_start, range_end):
                eventos.append(_serialize_client_event(item, occurrence_start, occurrence_end))
        eventos.sort(key=lambda entry: entry["start"].get("dateTime") or entry["start"].get("date") or "")
        return Response({"eventos": eventos})

    def post(self, request):
        serializer = ClientAgendaEventSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        event = serializer.save(tenant=request.user.tenant, created_by=request.user)
        return Response({"evento": _serialize_client_event(event, event.data_inicio, event.data_fim)}, status=status.HTTP_201_CREATED)

    def put(self, request):
        event_id = request.data.get("event_id")
        if not event_id:
            return Response({"detail": "event_id e obrigatorio para edicao."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            instance = ClientAgendaEvent.objects.get(pk=event_id, tenant=request.user.tenant)
        except ClientAgendaEvent.DoesNotExist:
            return Response({"detail": "Evento nao encontrado."}, status=status.HTTP_404_NOT_FOUND)

        serializer = ClientAgendaEventSerializer(instance, data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        event = serializer.save()
        return Response({"evento": _serialize_client_event(event, event.data_inicio, event.data_fim)}, status=status.HTTP_200_OK)


class ClientAgendaEventAttachmentsView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def get_event(self, pk, user):
        return ClientAgendaEvent.objects.get(pk=pk, tenant=user.tenant)

    def get(self, request, pk):
        try:
            event = self.get_event(pk, request.user)
        except ClientAgendaEvent.DoesNotExist:
            return Response({"detail": "Evento nao encontrado."}, status=status.HTTP_404_NOT_FOUND)

        content_type = ContentType.objects.get_for_model(ClientAgendaEvent)
        queryset = Attachment.objects.filter(
            tenant=event.tenant,
            content_type=content_type,
            object_id=event.pk,
        ).order_by("-created_at")
        return Response(AttachmentSerializer(queryset, many=True, context={"request": request}).data)

    def post(self, request, pk):
        try:
            event = self.get_event(pk, request.user)
        except ClientAgendaEvent.DoesNotExist:
            return Response({"detail": "Evento nao encontrado."}, status=status.HTTP_404_NOT_FOUND)

        files = request.FILES.getlist("files")
        if not files:
            return Response({"detail": "Nenhum arquivo enviado."}, status=status.HTTP_400_BAD_REQUEST)

        content_type = ContentType.objects.get_for_model(ClientAgendaEvent)
        created = [
            Attachment.create_from_upload(
                tenant=event.tenant,
                uploaded_by=request.user,
                content_type=content_type,
                object_id=event.pk,
                uploaded_file=uploaded_file,
            )
            for uploaded_file in files
        ]
        return Response(AttachmentSerializer(created, many=True, context={"request": request}).data, status=status.HTTP_201_CREATED)
