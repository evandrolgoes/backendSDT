from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.text import slugify
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from apps.clients.models import EconomicGroup, SubGroup
from .models import Role, Tenant, User, UserRole


class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = ["id", "name", "slug", "is_active", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]


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
    assigned_groups = serializers.PrimaryKeyRelatedField(many=True, queryset=EconomicGroup.objects.all(), required=False)
    assigned_subgroups = serializers.PrimaryKeyRelatedField(many=True, queryset=SubGroup.objects.all(), required=False)

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
            "username",
            "email",
            "full_name",
            "phone",
            "access_status",
            "is_active",
            "is_staff",
            "is_superuser",
            "assigned_groups",
            "assigned_subgroups",
            "password",
            "created_at",
            "user_roles",
        ]
        read_only_fields = ["created_at", "is_superuser"]

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
            if assigned_groups is not None:
                invalid_groups = [group.grupo or str(group.pk) for group in assigned_groups if group.tenant_id != tenant.id]
                if invalid_groups:
                    raise serializers.ValidationError({"assigned_groups": f"Todos os grupos atribuidos devem pertencer ao tenant {tenant}."})
            if assigned_subgroups is not None:
                invalid_subgroups = [subgroup.subgrupo or str(subgroup.pk) for subgroup in assigned_subgroups if subgroup.tenant_id != tenant.id]
                if invalid_subgroups:
                    raise serializers.ValidationError({"assigned_subgroups": f"Todos os subgrupos atribuidos devem pertencer ao tenant {tenant}."})
        return attrs


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
