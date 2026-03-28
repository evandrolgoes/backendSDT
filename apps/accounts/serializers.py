from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from apps.clients.models import EconomicGroup, SubGroup
from .constants import AVAILABLE_MODULE_CODES, AVAILABLE_MODULE_CHOICES
from .models import Invitation, Tenant, User


def send_invitation_email(invitation):
    invite_url = f"{settings.FRONTEND_URL.rstrip('/')}/abrir-conta/{invitation.token}"
    tenant_name = invitation.target_tenant_name or (invitation.tenant.name if invitation.tenant_id else "Hedge Position")
    subject = f"Convite para acessar {tenant_name}"
    message = (
        f"Voce recebeu um convite para criar sua conta em {tenant_name}.\n\n"
        f"Use o link abaixo para concluir seu cadastro:\n{invite_url}\n\n"
        f"Este convite expira em {invitation.expires_at.strftime('%d/%m/%Y')}."
    )
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [invitation.email], fail_silently=False)


class TenantSerializer(serializers.ModelSerializer):
    enabled_modules = serializers.ListField(
        child=serializers.ChoiceField(choices=AVAILABLE_MODULE_CHOICES),
        required=False,
        allow_empty=True,
    )
    class Meta:
        model = Tenant
        fields = [
            "id",
            "name",
            "slug",
            "requires_master_user",
            "can_send_invitations",
            "can_register_groups",
            "can_register_subgroups",
            "enabled_modules",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def validate_enabled_modules(self, value):
        if not value:
            return list(AVAILABLE_MODULE_CODES)
        return [module for module in AVAILABLE_MODULE_CODES if module in value]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if not attrs.get("enabled_modules"):
            attrs["enabled_modules"] = list(AVAILABLE_MODULE_CODES)
        return attrs

    def create(self, validated_data):
        if not validated_data.get("enabled_modules"):
            validated_data["enabled_modules"] = list(AVAILABLE_MODULE_CODES)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if "enabled_modules" in validated_data and not validated_data.get("enabled_modules"):
            validated_data["enabled_modules"] = list(AVAILABLE_MODULE_CODES)
        return super().update(instance, validated_data)


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)
    tenant_name = serializers.CharField(source="tenant.name", read_only=True)
    tenant_slug = serializers.CharField(source="tenant.slug", read_only=True)
    tenant_requires_master_user = serializers.BooleanField(source="tenant.requires_master_user", read_only=True)
    tenant_can_send_invitations = serializers.BooleanField(source="tenant.can_send_invitations", read_only=True)
    tenant_can_register_groups = serializers.BooleanField(source="tenant.can_register_groups", read_only=True)
    tenant_can_register_subgroups = serializers.BooleanField(source="tenant.can_register_subgroups", read_only=True)
    active_admin_invitations_count = serializers.SerializerMethodField()
    owned_groups_count = serializers.SerializerMethodField()
    owned_subgroups_count = serializers.SerializerMethodField()
    carteira_name = serializers.CharField(source="master_user.full_name", read_only=True)
    master_user_name = serializers.CharField(source="master_user.full_name", read_only=True)
    master_user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=False, allow_null=True)
    effective_modules = serializers.SerializerMethodField()
    dashboard_filter = serializers.JSONField(required=False)

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get("request")
        if request and getattr(request.user, "is_authenticated", False) and "tenant" in fields and not request.user.is_superuser:
            fields["tenant"] = serializers.HiddenField(default=request.user.tenant)
        tenant = None
        instance_obj = self.instance if isinstance(self.instance, User) else None
        if instance_obj is not None and instance_obj.tenant_id:
            tenant = instance_obj.tenant
        elif request and getattr(request.user, "is_authenticated", False) and not request.user.is_superuser:
            tenant = request.user.tenant
        if tenant is not None:
            if getattr(tenant, "requires_master_user", False):
                fields["master_user"].queryset = User.objects.all()
            else:
                fields["master_user"].queryset = User.objects.none()
        if request and getattr(request.user, "is_authenticated", False) and request.user.is_superuser:
            fields["master_user"].queryset = User.objects.all()
        return fields

    class Meta:
        model = User
        fields = [
            "id",
            "tenant",
            "tenant_name",
            "tenant_slug",
            "tenant_requires_master_user",
            "tenant_can_send_invitations",
            "tenant_can_register_groups",
            "tenant_can_register_subgroups",
            "active_admin_invitations_count",
            "owned_groups_count",
            "owned_subgroups_count",
            "carteira_name",
            "role",
            "master_user",
            "master_user_name",
            "username",
            "email",
            "full_name",
            "phone",
            "max_admin_invitations",
            "max_owned_groups",
            "max_owned_subgroups",
            "access_status",
            "is_active",
            "is_superuser",
            "effective_modules",
            "dashboard_filter",
            "password",
            "created_at",
        ]
        read_only_fields = ["created_at", "is_superuser", "effective_modules"]

    def get_effective_modules(self, obj):
        return obj.get_effective_modules()

    def get_active_admin_invitations_count(self, obj):
        return obj.get_active_admin_invitation_count()

    def get_owned_groups_count(self, obj):
        return obj.get_owned_groups_count()

    def get_owned_subgroups_count(self, obj):
        return obj.get_owned_subgroups_count()

    def validate_tenant(self, value):
        request = self.context["request"]
        if not getattr(request.user, "is_authenticated", False):
            return value
        if request.user.is_superuser:
            return value
        return request.user.tenant

    def create(self, validated_data):
        request = self.context["request"]
        password = validated_data.pop("password", None)
        if getattr(request.user, "is_authenticated", False) and not request.user.is_superuser:
            if request.user.has_tenant_slug("admin", "consultor"):
                validated_data["tenant"] = Tenant.objects.filter(slug="usuario").first() or request.user.tenant
                validated_data["master_user"] = request.user.get_master_root()
            else:
                validated_data["tenant"] = request.user.tenant
                validated_data["master_user"] = request.user.get_master_root()
        validated_data["allowed_modules"] = []
        validated_data.setdefault("role", User.Role.STAFF)
        user = User(**validated_data)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save()
        return user

    def update(self, instance, validated_data):
        request = self.context.get("request")
        password = validated_data.pop("password", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.allowed_modules = []
        if password:
            instance.set_password(password)
        instance.save()
        return instance

    def validate(self, attrs):
        attrs = super().validate(attrs)
        tenant = attrs["tenant"] if "tenant" in attrs else None
        if tenant is None and self.instance is not None:
            tenant = self.instance.tenant
        request = self.context.get("request")
        if tenant is None and request and getattr(request.user, "is_authenticated", False) and not request.user.is_superuser:
            tenant = request.user.tenant

        master_user = attrs["master_user"] if "master_user" in attrs else None
        if "master_user" not in attrs and self.instance is not None:
            master_user = self.instance.master_user
        if tenant is not None:
            assignment_tenant = tenant
            if getattr(tenant, "requires_master_user", False):
                if not master_user:
                    raise serializers.ValidationError({"master_user": "Usuarios deste tenant devem ter uma carteira vinculada."})
            else:
                attrs["master_user"] = None
        return attrs


class DashboardFilterSerializer(serializers.Serializer):
    grupo = serializers.ListField(child=serializers.CharField(), required=False, allow_empty=True)
    subgrupo = serializers.ListField(child=serializers.CharField(), required=False, allow_empty=True)
    cultura = serializers.ListField(child=serializers.CharField(), required=False, allow_empty=True)
    safra = serializers.ListField(child=serializers.CharField(), required=False, allow_empty=True)
    localidade = serializers.ListField(child=serializers.CharField(), required=False, allow_empty=True)

    def to_representation(self, instance):
        data = instance if isinstance(instance, dict) else {}
        return {
            "grupo": [str(item) for item in (data.get("grupo") or []) if item not in (None, "")],
            "subgrupo": [str(item) for item in (data.get("subgrupo") or []) if item not in (None, "")],
            "cultura": [str(item) for item in (data.get("cultura") or []) if item not in (None, "")],
            "safra": [str(item) for item in (data.get("safra") or []) if item not in (None, "")],
            "localidade": [str(item) for item in (data.get("localidade") or []) if item not in (None, "")],
        }

    def validate(self, attrs):
        normalized = self.to_representation(attrs)
        return normalized


class BaseInvitationSerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(source="tenant.name", read_only=True)
    invited_by_name = serializers.CharField(source="invited_by.full_name", read_only=True)
    accepted_user_name = serializers.CharField(source="accepted_user.full_name", read_only=True)
    invite_url = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = Invitation
        fields = [
            "id",
            "tenant",
            "tenant_name",
            "kind",
            "target_tenant_name",
            "target_tenant_slug",
            "email",
            "assigned_groups",
            "assigned_subgroups",
            "status",
            "expires_at",
            "invited_by",
            "invited_by_name",
            "full_name",
            "phone",
            "message",
            "accepted_user",
            "accepted_user_name",
            "invite_url",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["invited_by", "tenant_name", "invited_by_name", "accepted_user", "accepted_user_name", "created_at", "updated_at"]

    def get_fields(self):
        fields = super().get_fields()
        fields["assigned_groups"] = serializers.PrimaryKeyRelatedField(many=True, queryset=EconomicGroup.objects.all(), required=False)
        fields["assigned_subgroups"] = serializers.PrimaryKeyRelatedField(many=True, queryset=SubGroup.objects.all(), required=False)
        return fields

    def validate_tenant(self, value):
        return value

    def validate_email(self, value):
        return value.strip().lower()

    def get_invite_url(self, obj):
        return f"{settings.FRONTEND_URL.rstrip('/')}/abrir-conta/{obj.token}"

    def get_invitation_kind(self):
        return self.context.get("invitation_kind")

    def get_status(self, obj):
        if obj.expires_at and obj.expires_at < timezone.localdate() and obj.status == Invitation.Status.PENDING:
            return Invitation.Status.EXPIRED
        return obj.status

    def validate(self, attrs):
        attrs = super().validate(attrs)
        invitation_kind = self.get_invitation_kind()
        if not invitation_kind:
            invitation_kind = attrs.get("kind") or getattr(self.instance, "kind", None)
        if not invitation_kind:
            invitation_kind = Invitation.Kind.INTERNAL_USER
        attrs["kind"] = invitation_kind
        tenant = attrs.get("tenant")
        if tenant is None and self.instance is not None:
            tenant = self.instance.tenant
        request = self.context.get("request")

        email = attrs.get("email") or getattr(self.instance, "email", None)
        if email and User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError({"email": "Ja existe uma conta com este e-mail."})
        if tenant and email:
            duplicate_invite = Invitation.objects.filter(tenant=tenant, email__iexact=email).exclude(pk=getattr(self.instance, "pk", None))
            active_statuses = [Invitation.Status.PENDING]
            if duplicate_invite.filter(status__in=active_statuses, kind=invitation_kind).exists():
                raise serializers.ValidationError({"email": "Ja existe um convite ativo para este e-mail neste tenant."})
        request_user = getattr(request, "user", None)
        if invitation_kind == Invitation.Kind.PLATFORM_ADMIN:
            if request_user and getattr(request_user, "is_authenticated", False) and not request_user.is_superuser:
                requester_tenant_slug = getattr(getattr(request_user, "tenant", None), "slug", "")
                if requester_tenant_slug != "admin":
                    attrs["target_tenant_slug"] = "usuario"
                    attrs["target_tenant_name"] = Tenant.objects.filter(slug="usuario").values_list("name", flat=True).first() or "usuario"
                    target_tenant_slug = "usuario"
                else:
                    target_tenant_slug = slugify(attrs.get("target_tenant_slug") or getattr(self.instance, "target_tenant_slug", ""))
            else:
                target_tenant_slug = slugify(attrs.get("target_tenant_slug") or getattr(self.instance, "target_tenant_slug", ""))
            if not target_tenant_slug:
                raise serializers.ValidationError({"target_tenant_slug": "Selecione o tenant de destino do convite."})
            target_tenant = Tenant.objects.filter(slug=target_tenant_slug).first()
            if not target_tenant:
                raise serializers.ValidationError({"target_tenant_slug": "Tenant de destino invalido."})
            attrs["target_tenant_slug"] = target_tenant.slug
            attrs["target_tenant_name"] = target_tenant.name
        else:
            if tenant and not tenant.can_send_invitations:
                raise serializers.ValidationError({"tenant": "Este tenant nao possui direito a convites."})
            attrs["target_tenant_name"] = ""
            attrs["target_tenant_slug"] = ""

        if request_user and getattr(request_user, "is_authenticated", False) and not request_user.is_superuser:
            if invitation_kind == Invitation.Kind.PLATFORM_ADMIN:
                limit = request_user.max_admin_invitations
                if limit is not None:
                    active_count = request_user.get_active_admin_invitation_count()
                    if self.instance and getattr(self.instance, "status", None) == Invitation.Status.PENDING:
                        active_count = max(active_count - 1, 0)
                    if active_count >= limit:
                        raise serializers.ValidationError({"email": "Este usuario atingiu o limite de convites administrativos."})

        return attrs

    def create(self, validated_data):
        request = self.context.get("request")
        invitation_kind = validated_data.get("kind", self.get_invitation_kind())
        if request and getattr(request.user, "is_authenticated", False):
            validated_data["invited_by"] = request.user
        if invitation_kind != Invitation.Kind.PLATFORM_ADMIN and not validated_data.get("tenant"):
            raise serializers.ValidationError({"tenant": "Tenant obrigatorio para enviar convite."})
        validated_data.setdefault("full_name", "")
        validated_data.setdefault("phone", "")
        validated_data.setdefault("message", "")
        validated_data["status"] = Invitation.Status.PENDING
        validated_data.setdefault("expires_at", timezone.localdate() + timedelta(days=7))
        with transaction.atomic():
            invitation = super().create(validated_data)
            send_invitation_email(invitation)
        return invitation


class InvitationSerializer(BaseInvitationSerializer):
    pass


class AdminInvitationSerializer(BaseInvitationSerializer):
    class Meta(BaseInvitationSerializer.Meta):
        fields = BaseInvitationSerializer.Meta.fields


class InvitationLookupSerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(source="tenant.name", read_only=True)
    status = serializers.SerializerMethodField()

    def get_status(self, obj):
        if obj.expires_at and obj.expires_at < timezone.localdate() and obj.status == Invitation.Status.PENDING:
            return Invitation.Status.EXPIRED
        return obj.status

    class Meta:
        model = Invitation
        fields = ["email", "tenant_name", "target_tenant_name", "status", "expires_at", "kind"]


class InvitationAcceptSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=150)
    username = serializers.CharField(max_length=150)
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True, min_length=8)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        invitation = self.context["invitation"]
        tenant = invitation.tenant

        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "As senhas nao conferem."})

        if invitation.status != Invitation.Status.PENDING:
            raise serializers.ValidationError("Este convite nao esta mais disponivel.")

        if invitation.expires_at and invitation.expires_at < timezone.localdate():
            invitation.status = Invitation.Status.EXPIRED
            invitation.save(update_fields=["status", "updated_at"])
            raise serializers.ValidationError("Este convite expirou.")

        if User.objects.filter(email__iexact=invitation.email).exists():
            raise serializers.ValidationError({"email": "Ja existe uma conta com este e-mail."})

        if User.objects.filter(username__iexact=attrs["username"]).exists():
            raise serializers.ValidationError({"username": "Ja existe um usuario com esse nome de acesso."})

        return attrs

    @transaction.atomic
    def save(self, **kwargs):
        invitation = self.context["invitation"]
        root_user = invitation.invited_by.get_master_root() if invitation.invited_by_id else None
        target_tenant = invitation.tenant
        master_user = root_user
        role = User.Role.STAFF

        if invitation.kind == Invitation.Kind.PLATFORM_ADMIN:
            target_tenant = Tenant.objects.get(slug=invitation.target_tenant_slug)
            master_user = None
            role = User.Role.OWNER
        elif invitation.kind == Invitation.Kind.INTERNAL_USER:
            if target_tenant and target_tenant.requires_master_user:
                master_user = invitation.invited_by
            else:
                master_user = None
            role = User.Role.STAFF

        user = User(
            tenant=target_tenant,
            master_user=master_user,
            username=self.validated_data["username"].strip(),
            email=invitation.email,
            full_name=self.validated_data["full_name"].strip(),
            phone=self.validated_data.get("phone", "").strip(),
            role=role,
            access_status=User.AccessStatus.ACTIVE,
            allowed_modules=[],
            is_staff=False,
        )
        user.set_password(self.validated_data["password"])
        user.save()
        assigned_groups = list(invitation.assigned_groups.all())
        assigned_subgroups = list(invitation.assigned_subgroups.all())
        if assigned_groups:
            user.assigned_groups.set(assigned_groups)
            for group in assigned_groups:
                group.users_with_access.add(user)
        if assigned_subgroups:
            user.assigned_subgroups.set(assigned_subgroups)
            for subgroup in assigned_subgroups:
                subgroup.users_with_access.add(user)

        invitation.full_name = user.full_name
        invitation.phone = user.phone
        invitation.status = Invitation.Status.ACCEPTED
        invitation.accepted_user = user
        invitation.save(update_fields=["full_name", "phone", "status", "accepted_user", "updated_at"])
        return user


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        username_or_email = attrs["username"].strip()
        password = attrs["password"]

        user = authenticate(username=username_or_email, password=password)
        if not user and "@" in username_or_email:
            matched_user = User.objects.filter(email__iexact=username_or_email).first()
            if matched_user and matched_user.access_status == User.AccessStatus.PENDING:
                raise serializers.ValidationError("Seu acesso esta pendente de aprovacao.")
            if matched_user:
                user = authenticate(username=matched_user.username, password=password)

        if user and user.access_status == User.AccessStatus.PENDING:
            raise serializers.ValidationError("Seu acesso esta pendente de aprovacao.")
        if not user or not user.is_active:
            raise serializers.ValidationError("Credenciais inválidas.")
        refresh = RefreshToken.for_user(user)
        attrs["user"] = user
        attrs["access"] = str(refresh.access_token)
        attrs["refresh"] = str(refresh)
        return attrs


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def save(self):
        email = self.validated_data["email"].strip().lower()
        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if not user:
            return

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        reset_url = f"{settings.FRONTEND_URL.rstrip('/')}/reset-password?uid={uid}&token={token}"
        subject = "Redefinicao de senha - SDT Position"
        message = "\n".join(
            [
                f"Ola, {user.full_name or user.username}.",
                "",
                "Recebemos uma solicitacao para redefinir sua senha.",
                f"Acesse o link abaixo para criar uma nova senha:",
                reset_url,
                "",
                "Se voce nao solicitou esta alteracao, ignore este e-mail.",
            ]
        )
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)


class ResetPasswordConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate(self, attrs):
        try:
            user_id = force_str(urlsafe_base64_decode(attrs["uid"]))
            user = User.objects.get(pk=user_id, is_active=True)
        except Exception as exc:
            raise serializers.ValidationError({"uid": "Link de redefinicao invalido."}) from exc

        if not default_token_generator.check_token(user, attrs["token"]):
            raise serializers.ValidationError({"token": "Link de redefinicao invalido ou expirado."})

        attrs["user"] = user
        return attrs

    def save(self):
        user = self.validated_data["user"]
        user.set_password(self.validated_data["new_password"])
        user.save(update_fields=["password"])
        return user


class AccessRequestSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    company = serializers.CharField(max_length=150)
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True)
    message = serializers.CharField(required=False, allow_blank=True)

    def validate_email(self, value):
        email = value.strip().lower()
        existing_user = User.objects.filter(email__iexact=email).first()
        if existing_user:
            if existing_user.access_status == User.AccessStatus.PENDING:
                raise serializers.ValidationError("Ja existe uma solicitacao pendente para este e-mail.")
            raise serializers.ValidationError("Ja existe um usuario cadastrado com este e-mail.")
        return email

    def _build_username(self, email):
        base = slugify(email.split("@")[0]).replace("-", "_") or "usuario"
        username = base
        counter = 1
        while User.objects.filter(username=username).exists():
            counter += 1
            username = f"{base}_{counter}"
        return username

    def save(self):
        payload = self.validated_data
        email = payload["email"]

        user = User(
            username=self._build_username(email),
            email=email,
            full_name=payload["full_name"],
            phone=payload.get("phone", ""),
            access_status=User.AccessStatus.PENDING,
            is_staff=False,
        )
        user.set_unusable_password()
        user.save()

        subject = "Nova solicitacao de acesso - SDT Position"
        message = "\n".join(
            [
                "Uma nova solicitacao de acesso foi enviada no frontend.",
                "",
                f"Usuario criado: {user.username}",
                f"Status: {user.get_access_status_display()}",
                f"Nome: {payload['full_name']}",
                f"Email: {email}",
                f"Empresa: {payload['company']}",
                f"Telefone: {payload.get('phone') or '-'}",
                "",
                "Mensagem:",
                payload.get("message") or "-",
            ]
        )
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [settings.ACCESS_REQUEST_NOTIFY_EMAIL],
            fail_silently=False,
        )
        return user
