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
from .models import Invitation, Role, Tenant, User, UserRole


def send_invitation_email(invitation):
    invite_url = f"{settings.FRONTEND_URL.rstrip('/')}/abrir-conta/{invitation.token}"
    tenant_name = invitation.tenant.name if invitation.tenant_id else "Hedge Position"
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
    current_groups = serializers.SerializerMethodField()
    current_subgroups = serializers.SerializerMethodField()
    current_users = serializers.SerializerMethodField()
    current_invitations = serializers.SerializerMethodField()

    class Meta:
        model = Tenant
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "subscription_status",
            "expires_at",
            "max_groups",
            "max_subgroups",
            "max_users",
            "max_invitations",
            "enabled_modules",
            "current_groups",
            "current_subgroups",
            "current_users",
            "current_invitations",
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

    def get_current_groups(self, obj):
        return obj.economicgroups.count()

    def get_current_subgroups(self, obj):
        return obj.subgroups.count()

    def get_current_users(self, obj):
        return obj.users.filter(is_superuser=False).count()

    def get_current_invitations(self, obj):
        return obj.invitations.filter(status__in=[Invitation.Status.PENDING, Invitation.Status.SENT]).count()


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ["id", "code", "name"]


class UserRoleSerializer(serializers.ModelSerializer):
    role = RoleSerializer(read_only=True)
    role_id = serializers.PrimaryKeyRelatedField(source="role", queryset=Role.objects.all(), write_only=True)

    class Meta:
        model = UserRole
        fields = ["id", "role", "role_id"]


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)
    user_roles = UserRoleSerializer(many=True, read_only=True)
    tenant_name = serializers.CharField(source="tenant.name", read_only=True)
    tenant_slug = serializers.CharField(source="tenant.slug", read_only=True)
    tenant_description = serializers.CharField(source="tenant.description", read_only=True)
    tenant_max_groups = serializers.IntegerField(source="tenant.max_groups", read_only=True)
    tenant_max_subgroups = serializers.IntegerField(source="tenant.max_subgroups", read_only=True)
    tenant_max_users = serializers.IntegerField(source="tenant.max_users", read_only=True)
    tenant_max_invitations = serializers.IntegerField(source="tenant.max_invitations", read_only=True)
    tenant_current_groups = serializers.SerializerMethodField()
    tenant_current_subgroups = serializers.SerializerMethodField()
    tenant_current_users = serializers.SerializerMethodField()
    tenant_current_invitations = serializers.SerializerMethodField()
    assigned_groups = serializers.PrimaryKeyRelatedField(many=True, queryset=EconomicGroup.objects.all(), required=False)
    assigned_subgroups = serializers.PrimaryKeyRelatedField(many=True, queryset=SubGroup.objects.all(), required=False)
    effective_modules = serializers.SerializerMethodField()

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get("request")
        if request and getattr(request.user, "is_authenticated", False) and "tenant" in fields and not request.user.is_superuser:
            fields["tenant"] = serializers.HiddenField(default=request.user.tenant)
        tenant = None
        if request and getattr(request.user, "is_authenticated", False):
            tenant = None if request.user.is_superuser else request.user.tenant
        elif self.instance is not None:
            tenant = self.instance.tenant
        if tenant is not None:
            fields["assigned_groups"].queryset = EconomicGroup.objects.filter(tenant=tenant)
            fields["assigned_subgroups"].queryset = SubGroup.objects.filter(tenant=tenant)
        return fields

    class Meta:
        model = User
        fields = [
            "id",
            "tenant",
            "tenant_name",
            "tenant_slug",
            "tenant_description",
            "tenant_max_groups",
            "tenant_max_subgroups",
            "tenant_max_users",
            "tenant_max_invitations",
            "tenant_current_groups",
            "tenant_current_subgroups",
            "tenant_current_users",
            "tenant_current_invitations",
            "username",
            "email",
            "full_name",
            "phone",
            "user_type",
            "access_status",
            "is_active",
            "is_staff",
            "is_superuser",
            "assigned_groups",
            "assigned_subgroups",
            "effective_modules",
            "password",
            "created_at",
            "user_roles",
        ]
        read_only_fields = ["created_at", "is_superuser", "effective_modules"]

    def get_effective_modules(self, obj):
        return obj.get_effective_modules()

    def get_tenant_current_groups(self, obj):
        return obj.tenant.economicgroups.count() if obj.tenant_id else 0

    def get_tenant_current_subgroups(self, obj):
        return obj.tenant.subgroups.count() if obj.tenant_id else 0

    def get_tenant_current_users(self, obj):
        return obj.tenant.users.filter(is_superuser=False).count() if obj.tenant_id else 0

    def get_tenant_current_invitations(self, obj):
        if not obj.tenant_id:
            return 0
        return obj.tenant.invitations.filter(status__in=[Invitation.Status.PENDING, Invitation.Status.SENT]).count()

    def validate_tenant(self, value):
        request = self.context["request"]
        if not getattr(request.user, "is_authenticated", False):
            return value
        if request.user.is_superuser:
            return value
        return request.user.tenant

    def create(self, validated_data):
        assigned_groups = validated_data.pop("assigned_groups", [])
        assigned_subgroups = validated_data.pop("assigned_subgroups", [])
        password = validated_data.pop("password", None)
        if getattr(self.context["request"].user, "is_authenticated", False) and not self.context["request"].user.is_superuser:
            validated_data["tenant"] = self.context["request"].user.tenant
        validated_data["allowed_modules"] = []
        user = User(**validated_data)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save()
        if assigned_groups:
            user.assigned_groups.set(assigned_groups)
        if assigned_subgroups:
            user.assigned_subgroups.set(assigned_subgroups)
        return user

    def update(self, instance, validated_data):
        assigned_groups = validated_data.pop("assigned_groups", None)
        assigned_subgroups = validated_data.pop("assigned_subgroups", None)
        password = validated_data.pop("password", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.allowed_modules = []
        if password:
            instance.set_password(password)
        instance.save()
        if assigned_groups is not None:
            instance.assigned_groups.set(assigned_groups)
        if assigned_subgroups is not None:
            instance.assigned_subgroups.set(assigned_subgroups)
        return instance

    def validate(self, attrs):
        attrs = super().validate(attrs)
        tenant = attrs.get("tenant")
        if tenant is None and self.instance is not None:
            tenant = self.instance.tenant
        request = self.context.get("request")
        if tenant is None and request and getattr(request.user, "is_authenticated", False) and not request.user.is_superuser:
            tenant = request.user.tenant

        assigned_groups = attrs.get("assigned_groups")
        assigned_subgroups = attrs.get("assigned_subgroups")
        if tenant is not None:
            if self.instance is None and tenant.max_users is not None and tenant.users.count() >= tenant.max_users:
                raise serializers.ValidationError({"tenant": f"Limite de usuarios atingido para o tenant {tenant.name}."})
            if assigned_groups is not None:
                invalid_groups = [group.grupo or str(group.pk) for group in assigned_groups if group.tenant_id != tenant.id]
                if invalid_groups:
                    raise serializers.ValidationError({"assigned_groups": f"Todos os grupos atribuidos devem pertencer ao tenant {tenant}."})
            if assigned_subgroups is not None:
                invalid_subgroups = [subgroup.subgrupo or str(subgroup.pk) for subgroup in assigned_subgroups if subgroup.tenant_id != tenant.id]
                if invalid_subgroups:
                    raise serializers.ValidationError({"assigned_subgroups": f"Todos os subgrupos atribuidos devem pertencer ao tenant {tenant}."})
        return attrs


class InvitationSerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(source="tenant.name", read_only=True)
    invited_by_name = serializers.CharField(source="invited_by.full_name", read_only=True)
    invite_url = serializers.SerializerMethodField()

    class Meta:
        model = Invitation
        fields = [
            "id",
            "tenant",
            "tenant_name",
            "email",
            "status",
            "expires_at",
            "invited_by",
            "invited_by_name",
            "invite_url",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["invited_by", "tenant_name", "invited_by_name", "created_at", "updated_at"]

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get("request")
        if request and getattr(request.user, "is_authenticated", False) and "tenant" in fields and not request.user.is_superuser:
            fields["tenant"] = serializers.HiddenField(default=request.user.tenant)
        return fields

    def validate_tenant(self, value):
        request = self.context["request"]
        if not getattr(request.user, "is_authenticated", False):
            return value
        if request.user.is_superuser:
            return value
        return request.user.tenant

    def validate_email(self, value):
        return value.strip().lower()

    def get_invite_url(self, obj):
        return f"{settings.FRONTEND_URL.rstrip('/')}/abrir-conta/{obj.token}"

    def validate(self, attrs):
        attrs = super().validate(attrs)
        tenant = attrs.get("tenant")
        if tenant is None and self.instance is not None:
            tenant = self.instance.tenant
        request = self.context.get("request")
        if tenant is None and request and getattr(request.user, "is_authenticated", False) and not request.user.is_superuser:
            tenant = request.user.tenant

        email = attrs.get("email") or getattr(self.instance, "email", None)
        if tenant and email:
            existing_user = User.objects.filter(tenant=tenant, email__iexact=email).exclude(pk=getattr(self.instance, "user_id", None)).first()
            if existing_user:
                raise serializers.ValidationError({"email": "Ja existe um usuario com este e-mail neste tenant."})
            duplicate_invite = Invitation.objects.filter(tenant=tenant, email__iexact=email).exclude(pk=getattr(self.instance, "pk", None))
            active_statuses = [Invitation.Status.PENDING, Invitation.Status.SENT]
            if duplicate_invite.filter(status__in=active_statuses).exists():
                raise serializers.ValidationError({"email": "Ja existe um convite ativo para este e-mail neste tenant."})
            if self.instance is None and tenant.max_invitations is not None:
                active_invites = tenant.invitations.filter(status__in=active_statuses).count()
                if active_invites >= tenant.max_invitations:
                    raise serializers.ValidationError({"tenant": f"Limite de convites ativos atingido para o tenant {tenant.name}."})

        return attrs

    def create(self, validated_data):
        request = self.context.get("request")
        if request and getattr(request.user, "is_authenticated", False):
            validated_data["invited_by"] = request.user
            if not request.user.is_superuser:
                validated_data["tenant"] = request.user.tenant
        if not validated_data.get("tenant"):
            raise serializers.ValidationError({"tenant": "Tenant obrigatorio para enviar convite."})
        validated_data.setdefault("full_name", "")
        validated_data.setdefault("user_type", User.UserType.USER)
        validated_data["status"] = Invitation.Status.SENT
        validated_data.setdefault("expires_at", timezone.localdate() + timedelta(days=7))
        with transaction.atomic():
            invitation = super().create(validated_data)
            send_invitation_email(invitation)
        return invitation


class InvitationLookupSerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(source="tenant.name", read_only=True)

    class Meta:
        model = Invitation
        fields = ["email", "tenant_name", "status", "expires_at"]


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

        if invitation.status not in {Invitation.Status.PENDING, Invitation.Status.SENT}:
            raise serializers.ValidationError("Este convite nao esta mais disponivel.")

        if invitation.expires_at and invitation.expires_at < timezone.localdate():
            raise serializers.ValidationError("Este convite expirou.")

        if tenant.max_users is not None and tenant.users.filter(is_superuser=False).count() >= tenant.max_users:
            raise serializers.ValidationError("O tenant atingiu o limite de usuarios.")

        if User.objects.filter(email__iexact=invitation.email).exists():
            raise serializers.ValidationError({"email": "Ja existe uma conta com este e-mail."})

        if User.objects.filter(username__iexact=attrs["username"]).exists():
            raise serializers.ValidationError({"username": "Ja existe um usuario com esse nome de acesso."})

        return attrs

    @transaction.atomic
    def save(self, **kwargs):
        invitation = self.context["invitation"]
        user = User(
            tenant=invitation.tenant,
            username=self.validated_data["username"].strip(),
            email=invitation.email,
            full_name=self.validated_data["full_name"].strip(),
            phone=self.validated_data.get("phone", "").strip(),
            user_type=invitation.user_type,
            access_status=User.AccessStatus.ACTIVE,
            allowed_modules=[],
        )
        user.set_password(self.validated_data["password"])
        user.save()

        invitation.full_name = user.full_name
        invitation.phone = user.phone
        invitation.status = Invitation.Status.ACCEPTED
        invitation.save(update_fields=["full_name", "phone", "status", "updated_at"])
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
