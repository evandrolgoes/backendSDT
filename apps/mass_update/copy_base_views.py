from pathlib import Path

import dj_database_url
from django.conf import settings
from django.db import connections, transaction
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.auditing.context import suppress_audit_signals
from apps.mass_update.views import RESOURCE_REGISTRY, _get_resource_config, _get_serializer, _resolve_field_meta, _user_has_access


COPY_BASE_EXCLUDED_FIELDS = {"attachments", "password"}


def _ensure_copy_base_access(request):
    if request.user.is_superuser:
        return
    if getattr(request.user, "has_module_access", lambda *_args: False)("sys_copy_base"):
        return
    raise PermissionDenied("Voce nao possui acesso a ferramenta Copy Base.")


def _read_env_values(env_path):
    values = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _resolve_copy_base_database_targets():
    options = []
    for env_name in (".env.real", ".env.local", ".env"):
        env_path = Path(settings.BASE_DIR) / env_name
        if not env_path.exists():
            continue
        values = _read_env_values(env_path)
        database_url = values.get("DATABASE_URL", "").strip()
        if not database_url:
            continue

        host = dj_database_url.parse(database_url).get("HOST", "") if not database_url.startswith("sqlite") else "sqlite"
        if "render.com" in host:
            label = f"Render ({env_name})"
        elif database_url.startswith("sqlite"):
            label = f"SQLite local ({env_name})"
        else:
            label = f"{host or 'Database'} ({env_name})"

        options.append(
            {
                "value": env_name,
                "label": label,
                "databaseUrl": database_url,
            }
        )
    return options


def _get_copy_base_database_target(source_database):
    for item in _resolve_copy_base_database_targets():
        if item["value"] == source_database:
            return item
    raise serializers.ValidationError({"database": "Banco informado nao suportado."})


def _build_copy_base_database_config(database_url):
    parse_kwargs = {"conn_max_age": 0}
    if not database_url.startswith("sqlite"):
        parse_kwargs["ssl_require"] = True
    config = settings.DATABASES["default"].copy()
    config.update(dj_database_url.parse(database_url, **parse_kwargs))
    return config


def _ensure_copy_base_connection(database_name):
    target = _get_copy_base_database_target(database_name)
    alias = f"copy_base_{database_name.replace('.', '_').replace('-', '_')}"
    if alias not in connections.databases:
        connections.databases[alias] = _build_copy_base_database_config(target["databaseUrl"])
    return alias, target


def _build_copy_base_resource_metadata(resource, config, request):
    serializer = _get_serializer(config["viewset"], request)
    fields = []
    for field_name, serializer_field in serializer.fields.items():
        if field_name in COPY_BASE_EXCLUDED_FIELDS:
            continue
        meta = _resolve_field_meta(field_name, serializer_field)
        fields.append(
            {
                "name": meta["name"],
                "label": meta["label"],
                "type": meta["type"],
                "defaultLookup": meta["defaultLookup"],
            }
        )
    return {
        "resource": resource,
        "label": config["label"],
        "fields": fields,
    }


def _normalize_copy_base_resources(resources):
    if resources in (None, "", []):
        return []
    if isinstance(resources, str):
        return [resources]
    if isinstance(resources, (list, tuple, set)):
        return [str(item).strip() for item in resources if str(item).strip()]
    raise serializers.ValidationError({"resources": "Selecione ao menos um recurso valido."})


def _resolve_copy_base_resources(request, resources):
    normalized = _normalize_copy_base_resources(resources)
    allowed_resources = []
    for resource, config in RESOURCE_REGISTRY.items():
        if _user_has_access(request.user, config):
            allowed_resources.append(resource)

    if not normalized:
        raise serializers.ValidationError({"resources": "Selecione ao menos um recurso para copiar."})

    if "all" in normalized:
        return allowed_resources

    invalid_resources = [resource for resource in normalized if resource not in allowed_resources]
    if invalid_resources:
        raise serializers.ValidationError({"resources": f"Recursos nao suportados: {', '.join(invalid_resources)}."})
    return normalized


def _get_copy_base_queryset(request, source_database, resource):
    config = _get_resource_config(request, resource)
    alias, source_target = _ensure_copy_base_connection(source_database)
    model = config["viewset"].serializer_class.Meta.model
    queryset = model._default_manager.using(alias).all()
    return queryset.distinct(), config, alias, source_target


def _copy_model_instance(instance, source_alias, target_alias):
    model = instance.__class__
    target_manager = model._default_manager.using(target_alias)
    pk_attname = model._meta.pk.attname
    concrete_values = {}

    for field in model._meta.concrete_fields:
        if field.auto_created and not field.primary_key:
            continue
        concrete_values[field.attname] = getattr(instance, field.attname)

    pk_value = concrete_values.pop(pk_attname)
    target = target_manager.filter(pk=pk_value).first()
    created = target is None

    if created:
        target = model(**{pk_attname: pk_value, **concrete_values})
        target.save_base(using=target_alias, raw=True, force_insert=True)
    else:
        for field_name, value in concrete_values.items():
            setattr(target, field_name, value)
        target.save_base(using=target_alias, raw=True, force_update=True)

    for field in model._meta.many_to_many:
        source_ids = list(getattr(instance, field.name).all().using(source_alias).values_list("pk", flat=True))
        getattr(target, field.name).set(source_ids)

    return target, created


class CopyBaseTargetsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        _ensure_copy_base_access(request)
        resources = []
        for resource, config in RESOURCE_REGISTRY.items():
            if not _user_has_access(request.user, config):
                continue
            metadata = _build_copy_base_resource_metadata(resource, config, request)
            resources.append(
                {
                    "value": resource,
                    "label": config["label"],
                    "fields": metadata["fields"],
                }
            )

        return Response(
            {
                "databases": [{"value": item["value"], "label": item["label"]} for item in _resolve_copy_base_database_targets()],
                "resources": resources,
            }
        )


class CopyBasePreviewView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        _ensure_copy_base_access(request)
        source_database = request.data.get("sourceDatabase")
        target_database = request.data.get("targetDatabase")
        resources = _resolve_copy_base_resources(request, request.data.get("resources"))

        if not source_database:
            raise serializers.ValidationError({"sourceDatabase": "Banco de origem obrigatorio."})
        if not target_database:
            raise serializers.ValidationError({"targetDatabase": "Banco de destino obrigatorio."})
        if source_database == target_database:
            raise serializers.ValidationError({"targetDatabase": "Origem e destino precisam ser diferentes."})

        _target_alias, target_target = _ensure_copy_base_connection(target_database)
        resource_summaries = []
        total_matches = 0
        sample_rows = []

        for resource in resources:
            queryset, config, _source_alias, source_target = _get_copy_base_queryset(request, source_database, resource)
            match_count = queryset.count()
            total_matches += match_count
            resource_summaries.append(
                {
                    "resource": resource,
                    "resourceLabel": config["label"],
                    "matchCount": match_count,
                }
            )
            if len(sample_rows) < 5:
                remaining_slots = 5 - len(sample_rows)
                sample_rows.extend(_get_serializer(config["viewset"], request, queryset[:remaining_slots], many=True).data)

        return Response(
            {
                "sourceDatabase": source_database,
                "sourceDatabaseLabel": source_target["label"],
                "targetDatabase": target_database,
                "targetDatabaseLabel": target_target["label"],
                "resources": resource_summaries,
                "resourceCount": len(resource_summaries),
                "matchCount": total_matches,
                "sampleRows": sample_rows[:5],
            }
        )


class CopyBaseApplyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        _ensure_copy_base_access(request)
        source_database = request.data.get("sourceDatabase")
        target_database = request.data.get("targetDatabase")
        resources = _resolve_copy_base_resources(request, request.data.get("resources"))

        if not source_database:
            raise serializers.ValidationError({"sourceDatabase": "Banco de origem obrigatorio."})
        if not target_database:
            raise serializers.ValidationError({"targetDatabase": "Banco de destino obrigatorio."})
        if source_database == target_database:
            raise serializers.ValidationError({"targetDatabase": "Origem e destino precisam ser diferentes."})

        source_alias, source_target = _ensure_copy_base_connection(source_database)
        target_alias, target_target = _ensure_copy_base_connection(target_database)
        created_count = 0
        updated_count = 0
        sample_ids = []
        resource_results = []

        with transaction.atomic():
            with suppress_audit_signals():
                for resource in resources:
                    queryset, config, _query_source_alias, _source_target = _get_copy_base_queryset(request, source_database, resource)
                    resource_created = 0
                    resource_updated = 0
                    for instance in queryset.iterator():
                        target, created = _copy_model_instance(instance, source_alias, target_alias)
                        if created:
                            created_count += 1
                            resource_created += 1
                        else:
                            updated_count += 1
                            resource_updated += 1
                        if len(sample_ids) < 20:
                            sample_ids.append(f"{resource}:{target.pk}")
                    resource_results.append(
                        {
                            "resource": resource,
                            "resourceLabel": config["label"],
                            "copiedCount": resource_created + resource_updated,
                            "createdCount": resource_created,
                            "updatedCount": resource_updated,
                        }
                    )

        return Response(
            {
                "sourceDatabase": source_database,
                "sourceDatabaseLabel": source_target["label"],
                "targetDatabase": target_database,
                "targetDatabaseLabel": target_target["label"],
                "resources": resource_results,
                "resourceCount": len(resource_results),
                "copiedCount": created_count + updated_count,
                "createdCount": created_count,
                "updatedCount": updated_count,
                "sampleIds": sample_ids,
            }
        )
