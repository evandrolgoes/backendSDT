from django.contrib.auth import authenticate
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

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

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get("request")
        if request and getattr(request.user, "is_authenticated", False) and "tenant" in fields and not request.user.is_superuser:
            fields["tenant"] = serializers.HiddenField(default=request.user.tenant)
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
            "is_active",
            "is_staff",
            "is_superuser",
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
        password = validated_data.pop("password", None)
        if getattr(self.context["request"].user, "is_authenticated", False) and not self.context["request"].user.is_superuser:
            validated_data["tenant"] = self.context["request"].user.tenant
        user = User(**validated_data)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        username_or_email = attrs["username"].strip()
        password = attrs["password"]

        user = authenticate(username=username_or_email, password=password)
        if not user and "@" in username_or_email:
            matched_user = User.objects.filter(email__iexact=username_or_email).first()
            if matched_user:
                user = authenticate(username=matched_user.username, password=password)

        if not user or not user.is_active:
            raise serializers.ValidationError("Credenciais inválidas.")
        refresh = RefreshToken.for_user(user)
        attrs["user"] = user
        attrs["access"] = str(refresh.access_token)
        attrs["refresh"] = str(refresh)
        return attrs
