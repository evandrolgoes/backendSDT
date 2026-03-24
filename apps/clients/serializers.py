from django.utils import timezone
from rest_framework import serializers

from apps.accounts.models import User

from .models import (
    Broker,
    ClientAccount,
    Counterparty,
    CropSeason,
    EconomicGroup,
    GroupAccessRequest,
    SubGroup,
    SubGroupAccessRequest,
)


def get_effective_data_tenant(user):
    if not user or not getattr(user, "tenant_id", None):
        return None
    tenant = user.tenant
    if getattr(tenant, "requires_master_user", False) and user.master_user_id:
        return user.master_user.tenant
    return tenant


class TenantScopedSerializer(serializers.ModelSerializer):
    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get("request")
        if request and "tenant" in fields and getattr(request.user, "tenant_id", None):
            fields["tenant"] = serializers.HiddenField(default=request.user.tenant)
        return fields

    def validate(self, attrs):
        attrs = super().validate(attrs)
        request = self.context.get("request")
        if request and not request.user.tenant_id:
            raise serializers.ValidationError({"tenant": "O usuario autenticado nao possui tenant vinculado."})
        if request and "tenant" in self.fields and request.user.tenant_id:
            attrs["tenant"] = request.user.tenant
        return attrs

    def validate_tenant(self, value):
        request = self.context["request"]
        return request.user.tenant if request.user.tenant_id else value


class ClientAccountSerializer(TenantScopedSerializer):
    def validate(self, attrs):
        attrs = super().validate(attrs)
        tenant = attrs.get("tenant") or getattr(self.instance, "tenant", None)
        document = attrs.get("document")
        if tenant and document:
            queryset = ClientAccount.objects.filter(tenant=tenant, document=document)
            if self.instance:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.exists():
                raise serializers.ValidationError({"document": "Ja existe um cliente com este documento neste tenant."})
        return attrs

    class Meta:
        model = ClientAccount
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at"]
        validators = []


class BaseAccessOwnedSerializer(TenantScopedSerializer):
    owner_name = serializers.CharField(source="owner.full_name", read_only=True)
    users_with_access_names = serializers.SerializerMethodField()

    def get_users_with_access_names(self, obj):
        return list(obj.users_with_access.values_list("full_name", flat=True))

    def get_fields(self):
        fields = super().get_fields()
        fields["owner"] = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=False, allow_null=True)
        fields["users_with_access"] = serializers.PrimaryKeyRelatedField(many=True, queryset=User.objects.all(), required=False)
        return fields

    def _validate_owner_limit(self, owner):
        if owner is None or owner.is_superuser:
            return
        if isinstance(self, EconomicGroupSerializer):
            limit = owner.max_owned_groups
            if limit is None:
                return
            current_count = owner.owned_groups.exclude(pk=getattr(self.instance, "pk", None)).count()
            if current_count >= limit:
                raise serializers.ValidationError({"owner": "Este usuario atingiu o limite de grupos como proprietario."})
        elif isinstance(self, SubGroupSerializer):
            limit = owner.max_owned_subgroups
            if limit is None:
                return
            current_count = owner.owned_subgroups.exclude(pk=getattr(self.instance, "pk", None)).count()
            if current_count >= limit:
                raise serializers.ValidationError({"owner": "Este usuario atingiu o limite de subgrupos como proprietario."})

    def _validate_unique_name(self, attrs):
        if isinstance(self, EconomicGroupSerializer):
            field_name = "grupo"
            model = EconomicGroup
            message = "Ja existe um grupo com este nome."
        elif isinstance(self, SubGroupSerializer):
            field_name = "subgrupo"
            model = SubGroup
            message = "Ja existe um subgrupo com este nome."
        else:
            return

        raw_value = attrs.get(field_name, getattr(self.instance, field_name, None))
        value = (raw_value or "").strip()
        if not value:
            return

        attrs[field_name] = value
        queryset = model.objects.filter(**{f"{field_name}__iexact": value})
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError({field_name: message})

    def validate(self, attrs):
        attrs = super().validate(attrs)
        tenant = attrs.get("tenant") or getattr(self.instance, "tenant", None)
        request = self.context.get("request")
        if request and getattr(request.user, "is_authenticated", False) and self.instance is None:
            if isinstance(self, EconomicGroupSerializer) and not request.user.is_superuser and not getattr(request.user.tenant, "can_register_groups", False):
                raise serializers.ValidationError({"tenant": "Este tenant nao possui direito ao cadastro de grupos."})
            if isinstance(self, SubGroupSerializer) and not request.user.is_superuser and not getattr(request.user.tenant, "can_register_subgroups", False):
                raise serializers.ValidationError({"tenant": "Este tenant nao possui direito ao cadastro de subgrupos."})
        self._validate_unique_name(attrs)
        owner = attrs.get("owner", getattr(self.instance, "owner", None))
        if owner is None:
            if request and getattr(request.user, "is_authenticated", False):
                owner = request.user
                attrs["owner"] = owner
        self._validate_owner_limit(owner)
        users_with_access = attrs.get("users_with_access")
        return attrs

    def _sync_access_relations(self, instance):
        owner = instance.owner
        if owner:
            instance.users_with_access.add(owner)
            relation_name = "assigned_groups" if isinstance(instance, EconomicGroup) else "assigned_subgroups"
            getattr(owner, relation_name).add(instance)

    def create(self, validated_data):
        users_with_access = validated_data.pop("users_with_access", [])
        instance = super().create(validated_data)
        if users_with_access:
            instance.users_with_access.set(users_with_access)
        self._sync_access_relations(instance)
        if users_with_access:
            relation_name = "assigned_groups" if isinstance(instance, EconomicGroup) else "assigned_subgroups"
            for user in users_with_access:
                getattr(user, relation_name).add(instance)
        return instance

    def update(self, instance, validated_data):
        users_with_access = validated_data.pop("users_with_access", None)
        instance = super().update(instance, validated_data)
        if users_with_access is not None:
            instance.users_with_access.set(users_with_access)
        self._sync_access_relations(instance)
        if users_with_access is not None:
            relation_name = "assigned_groups" if isinstance(instance, EconomicGroup) else "assigned_subgroups"
            for user in instance.users_with_access.all():
                getattr(user, relation_name).add(instance)
        return instance


class EconomicGroupSerializer(BaseAccessOwnedSerializer):
    class Meta:
        model = EconomicGroup
        fields = ["id", "tenant", "grupo", "owner", "owner_name", "users_with_access", "users_with_access_names"]


class SubGroupSerializer(BaseAccessOwnedSerializer):
    class Meta:
        model = SubGroup
        fields = ["id", "tenant", "subgrupo", "descricao", "owner", "owner_name", "users_with_access", "users_with_access_names"]


class CropSeasonSerializer(TenantScopedSerializer):
    class Meta:
        model = CropSeason
        fields = "__all__"


class CounterpartySerializer(TenantScopedSerializer):
    class Meta:
        model = Counterparty
        fields = "__all__"


class BrokerSerializer(TenantScopedSerializer):
    class Meta:
        model = Broker
        fields = "__all__"


class GroupAccessRequestSerializer(serializers.ModelSerializer):
    requester_name = serializers.CharField(source="requester.full_name", read_only=True)
    requester_email = serializers.EmailField(source="requester.email", read_only=True)
    group_name = serializers.CharField(source="group.grupo", read_only=True)
    owner_name = serializers.CharField(source="group.owner.full_name", read_only=True)

    class Meta:
        model = GroupAccessRequest
        fields = [
            "id",
            "requester",
            "requester_name",
            "requester_email",
            "group",
            "group_name",
            "owner_name",
            "status",
            "reviewed_at",
            "reviewed_by",
            "created_at",
        ]
        read_only_fields = fields


class SubGroupAccessRequestSerializer(serializers.ModelSerializer):
    requester_name = serializers.CharField(source="requester.full_name", read_only=True)
    requester_email = serializers.EmailField(source="requester.email", read_only=True)
    subgroup_name = serializers.CharField(source="subgroup.subgrupo", read_only=True)
    owner_name = serializers.CharField(source="subgroup.owner.full_name", read_only=True)

    class Meta:
        model = SubGroupAccessRequest
        fields = [
            "id",
            "requester",
            "requester_name",
            "requester_email",
            "subgroup",
            "subgroup_name",
            "owner_name",
            "status",
            "reviewed_at",
            "reviewed_by",
            "created_at",
        ]
        read_only_fields = fields


class AccessRequestBulkSerializer(serializers.Serializer):
    names = serializers.ListField(child=serializers.CharField(max_length=120), allow_empty=False)

    def validate_names(self, value):
        cleaned = [item.strip() for item in value if str(item).strip()]
        if not cleaned:
            raise serializers.ValidationError("Informe pelo menos um nome.")
        return cleaned


def create_group_access_requests(names, requester):
    created = []
    for name in names:
        groups = (
            EconomicGroup.objects.filter(grupo__iexact=name, owner__isnull=False)
            .exclude(users_with_access=requester)
            .exclude(owner=requester)
            .select_related("owner")
        )
        for group in groups:
            request, was_created = GroupAccessRequest.objects.get_or_create(
                requester=requester,
                group=group,
                status=GroupAccessRequest.Status.PENDING,
            )
            if was_created:
                created.append(request)
    return created


def create_subgroup_access_requests(names, requester):
    created = []
    for name in names:
        subgroups = (
            SubGroup.objects.filter(subgrupo__iexact=name, owner__isnull=False)
            .exclude(users_with_access=requester)
            .exclude(owner=requester)
            .select_related("owner")
        )
        for subgroup in subgroups:
            request, was_created = SubGroupAccessRequest.objects.get_or_create(
                requester=requester,
                subgroup=subgroup,
                status=SubGroupAccessRequest.Status.PENDING,
            )
            if was_created:
                created.append(request)
    return created


def approve_group_access_request(access_request, reviewer):
    access_request.status = GroupAccessRequest.Status.APPROVED
    access_request.reviewed_at = timezone.now()
    access_request.reviewed_by = reviewer
    access_request.save(update_fields=["status", "reviewed_at", "reviewed_by"])
    access_request.group.users_with_access.add(access_request.requester)
    access_request.requester.assigned_groups.add(access_request.group)


def reject_group_access_request(access_request, reviewer):
    access_request.status = GroupAccessRequest.Status.REJECTED
    access_request.reviewed_at = timezone.now()
    access_request.reviewed_by = reviewer
    access_request.save(update_fields=["status", "reviewed_at", "reviewed_by"])


def approve_subgroup_access_request(access_request, reviewer):
    access_request.status = SubGroupAccessRequest.Status.APPROVED
    access_request.reviewed_at = timezone.now()
    access_request.reviewed_by = reviewer
    access_request.save(update_fields=["status", "reviewed_at", "reviewed_by"])
    access_request.subgroup.users_with_access.add(access_request.requester)
    access_request.requester.assigned_subgroups.add(access_request.subgroup)


def reject_subgroup_access_request(access_request, reviewer):
    access_request.status = SubGroupAccessRequest.Status.REJECTED
    access_request.reviewed_at = timezone.now()
    access_request.reviewed_by = reviewer
    access_request.save(update_fields=["status", "reviewed_at", "reviewed_by"])
