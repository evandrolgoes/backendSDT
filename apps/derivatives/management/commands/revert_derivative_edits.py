"""Reverte edicoes erradas de DerivativeOperation feitas por um usuario em um dia.

Usa a trilha de auditoria (apps.auditing.AuditLog): para cada operacao editada
pelo usuario no dia informado, restaura o valor anterior (`before`) APENAS nos
campos que aquele usuario alterou naquele dia.

Seguro por padrao:
  - dry-run (nao grava nada) ate passar --apply;
  - se o valor atual no banco difere do `after` registrado, o campo foi mexido
    depois -> nao reverte, marca para revisao manual;
  - campos de relacao (FK) alterados nao sao revertidos automaticamente
    (mapeamento texto->objeto e ambiguo) -> revisao manual;
  - campo que ja esta no valor correto e ignorado (idempotente);
  - tudo dentro de uma transacao.

Exemplos:
  python manage.py revert_derivative_edits --user fulano@dominio.com --date 2026-05-15
  python manage.py revert_derivative_edits --user fulano@dominio.com --date 2026-05-15 --report /tmp/revert.json
  python manage.py revert_derivative_edits --user fulano@dominio.com --date 2026-05-15 --apply
"""

import datetime as dt
import json
from decimal import Decimal, InvalidOperation

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.auditing.models import AuditLog
from apps.auditing.services import serialize_instance_for_log
from apps.derivatives.models import DerivativeOperation

ACTION = "alterado"


def _coerce(model_field, value):
    """Converte o valor serializado da auditoria para o tipo do campo do model."""
    if value is None:
        return None
    internal = model_field.get_internal_type()
    if internal == "DecimalField":
        return Decimal(str(value))
    if internal == "DateField":
        return dt.date.fromisoformat(value)
    if internal == "DateTimeField":
        return dt.datetime.fromisoformat(value)
    if internal in {"IntegerField", "PositiveIntegerField", "BigIntegerField", "PositiveBigIntegerField", "SmallIntegerField"}:
        return int(value)
    return value


def _eq(model_field, a, b):
    """Igualdade tolerante: Decimal comparado como Decimal, resto direto."""
    if a is None or b is None:
        return a is None and b is None
    if model_field.get_internal_type() == "DecimalField":
        try:
            return Decimal(str(a)) == Decimal(str(b))
        except (InvalidOperation, ValueError):
            return str(a) == str(b)
    return a == b


class Command(BaseCommand):
    help = "Reverte edicoes erradas de DerivativeOperation feitas por um usuario num dia (via AuditLog)."

    def add_arguments(self, parser):
        parser.add_argument("--user", required=True, help="id, username ou e-mail do usuario que fez as edicoes erradas")
        parser.add_argument("--date", required=True, help="dia das edicoes erradas, formato YYYY-MM-DD (fuso America/Sao_Paulo)")
        parser.add_argument("--apply", action="store_true", help="grava as reversoes (sem isso, apenas dry-run)")
        parser.add_argument("--report", default=None, help="caminho opcional para salvar um relatorio JSON do que foi/seria feito")

    def _resolve_user(self, ident):
        User = get_user_model()
        qs = User.objects.all()
        if ident.isdigit():
            user = qs.filter(pk=int(ident)).first()
            if user:
                return user
        return qs.filter(username=ident).first() or qs.filter(email__iexact=ident).first()

    def handle(self, *args, **opts):
        user = self._resolve_user(opts["user"])
        if not user:
            raise CommandError(f"Usuario nao encontrado: {opts['user']!r}")

        try:
            day = dt.date.fromisoformat(opts["date"])
        except ValueError:
            raise CommandError("--date invalido; use YYYY-MM-DD")

        tz = timezone.get_default_timezone()
        start = timezone.make_aware(dt.datetime.combine(day, dt.time.min), tz)
        end = start + dt.timedelta(days=1)

        ct = ContentType.objects.get_for_model(DerivativeOperation)
        fk_fields = {f.name for f in DerivativeOperation._meta.fields if f.is_relation}

        logs = list(
            AuditLog.objects.filter(
                content_type=ct, action=ACTION, user=user,
                created_at__gte=start, created_at__lt=end,
            ).order_by("object_id", "created_at")
        )

        self.stdout.write(
            f"Usuario: {user} (id={user.pk}) | dia {day.isoformat()} "
            f"({start.isoformat()} -> {end.isoformat()})"
        )
        self.stdout.write(f"Logs 'alterado' de DerivativeOperation nesse recorte: {len(logs)}")
        if not logs:
            self.stdout.write(self.style.WARNING("Nada a fazer."))
            return

        by_obj = {}
        for log in logs:
            by_obj.setdefault(log.object_id, []).append(log)

        report = {
            "user": str(user), "user_id": user.pk, "date": day.isoformat(),
            "apply": bool(opts["apply"]), "objects": [],
        }
        total_revert = total_manual = total_ok = total_missing = 0

        with transaction.atomic():
            for object_id, obj_logs in by_obj.items():
                obj = DerivativeOperation.objects.filter(pk=object_id).select_for_update().first()
                first_before = obj_logs[0].changes_json.get("before", {})
                last_after = obj_logs[-1].changes_json.get("after", {})

                entry = {
                    "object_id": object_id,
                    "cod_operacao_mae": (first_before.get("cod_operacao_mae") if obj is None else obj.cod_operacao_mae),
                    "edits_no_dia": len(obj_logs),
                    "fields": [],
                }

                if obj is None:
                    total_missing += 1
                    entry["status"] = "REGISTRO NAO EXISTE MAIS (excluido depois) - revisao manual"
                    report["objects"].append(entry)
                    self.stdout.write(self.style.ERROR(
                        f"  obj {object_id}: nao existe mais no banco -> revisao manual"
                    ))
                    continue

                changed_fields = sorted({
                    c["campo"] for lg in obj_logs for c in lg.changes_json.get("changes", [])
                })
                current = serialize_instance_for_log(obj)
                updates = {}

                self.stdout.write(
                    f"  obj {object_id} ({obj.cod_operacao_mae or '-'}): "
                    f"{len(obj_logs)} edicao(oes), campos tocados: {', '.join(changed_fields) or '-'}"
                )

                for fname in changed_fields:
                    target = first_before.get(fname)
                    expected = last_after.get(fname)
                    cur = current.get(fname)
                    finfo = {"campo": fname, "atual": cur, "restaurar_para": target, "after_auditado": expected}

                    if fname not in {f.name for f in DerivativeOperation._meta.fields}:
                        finfo["acao"] = "ignorado (campo nao e do model)"
                        entry["fields"].append(finfo)
                        continue

                    mf = DerivativeOperation._meta.get_field(fname)

                    if fname in fk_fields:
                        finfo["acao"] = "REVISAO MANUAL (campo de relacao/FK)"
                        total_manual += 1
                        entry["fields"].append(finfo)
                        self.stdout.write(self.style.WARNING(
                            f"    - {fname}: FK alterada ({cur!r} -> deveria voltar p/ {target!r}) -> revisao manual"
                        ))
                        continue

                    if _eq(mf, cur, target):
                        finfo["acao"] = "ok (ja esta no valor correto)"
                        total_ok += 1
                        entry["fields"].append(finfo)
                        continue

                    if not _eq(mf, cur, expected):
                        finfo["acao"] = "REVISAO MANUAL (valor atual difere do after auditado: mexido depois)"
                        total_manual += 1
                        entry["fields"].append(finfo)
                        self.stdout.write(self.style.WARNING(
                            f"    - {fname}: atual={cur!r} != after auditado={expected!r} "
                            f"-> alterado depois, NAO sera revertido (revisao manual)"
                        ))
                        continue

                    updates[fname] = _coerce(mf, target)
                    finfo["acao"] = "reverter" if opts["apply"] else "reverteria (dry-run)"
                    total_revert += 1
                    entry["fields"].append(finfo)
                    self.stdout.write(
                        f"    - {fname}: {cur!r} -> {target!r}"
                    )

                if updates:
                    entry["status"] = "REVERTIDO" if opts["apply"] else "REVERTERIA (dry-run)"
                    if opts["apply"]:
                        for k, v in updates.items():
                            setattr(obj, k, v)
                        obj.save(update_fields=list(updates.keys()))
                else:
                    entry["status"] = "sem campos para reverter"
                report["objects"].append(entry)

            self.stdout.write("")
            self.stdout.write(
                f"Resumo: {len(by_obj)} operacao(oes) | campos a reverter: {total_revert} | "
                f"ja ok: {total_ok} | revisao manual: {total_manual} | registros sumidos: {total_missing}"
            )

            if not opts["apply"]:
                self.stdout.write(self.style.WARNING(
                    "DRY-RUN: nada foi gravado. Rode de novo com --apply para aplicar."
                ))
                # Garante que um dry-run nunca persista nada.
                transaction.set_rollback(True)
            else:
                self.stdout.write(self.style.SUCCESS("Reversoes aplicadas e commitadas."))

        if opts["report"]:
            with open(opts["report"], "w", encoding="utf-8") as fh:
                json.dump(report, fh, ensure_ascii=False, indent=2, default=str)
            self.stdout.write(f"Relatorio salvo em {opts['report']}")
