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

Desfazer um --apply anterior (devolve ao estado pre-revert; mesmo dry-run/transacao):
  python manage.py revert_derivative_edits --undo-apply-on 2026-05-19 --objects 706,707,742,743,744,745,746,757
  python manage.py revert_derivative_edits --undo-apply-on 2026-05-19 --objects 706,707,742,743,744,745,746,757 --apply
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
        parser.add_argument("--user", default=None, help="id, username ou e-mail do usuario que fez as edicoes erradas (modo reverter)")
        parser.add_argument("--date", default=None, help="dia das edicoes erradas, formato YYYY-MM-DD (fuso America/Sao_Paulo)")
        parser.add_argument(
            "--undo-apply-on", default=None,
            help="DESFAZER um --apply anterior: data YYYY-MM-DD em que este comando rodou com --apply "
                 "(reverte os logs de auditoria gerados pelo proprio comando, user nulo). Devolve ao estado pre-revert.",
        )
        parser.add_argument("--objects", default=None, help="opcional: lista de IDs separados por virgula para restringir o escopo (ex: 706,707,742)")
        parser.add_argument(
            "--include-fk", action="store_true",
            help="tambem reverte campos de relacao (FK), resolvendo o texto auditado p/ o objeto. "
                 "FK ambiguo/nao encontrado vira revisao manual (nao grava esse campo).",
        )
        parser.add_argument("--apply", action="store_true", help="grava as reversoes (sem isso, apenas dry-run)")
        parser.add_argument("--report", default=None, help="caminho opcional para salvar um relatorio JSON do que foi/seria feito")

    def _resolve_fk(self, model_field, target_str):
        """Acha o(s) objeto(s) do model relacionado cujo str() == texto auditado."""
        rel = model_field.related_model
        if rel is None:
            return []
        return [o for o in rel._default_manager.all() if str(o) == target_str]

    def _resolve_user(self, ident):
        User = get_user_model()
        qs = User.objects.all()
        if ident.isdigit():
            user = qs.filter(pk=int(ident)).first()
            if user:
                return user
        return qs.filter(username=ident).first() or qs.filter(email__iexact=ident).first()

    def handle(self, *args, **opts):
        undo_mode = bool(opts.get("undo_apply_on"))

        if undo_mode:
            if opts.get("user") or opts.get("date"):
                raise CommandError("--undo-apply-on nao pode ser combinado com --user/--date.")
            user = None
            try:
                day = dt.date.fromisoformat(opts["undo_apply_on"])
            except ValueError:
                raise CommandError("--undo-apply-on invalido; use YYYY-MM-DD")
        else:
            if not opts.get("user") or not opts.get("date"):
                raise CommandError("Modo reverter exige --user e --date (ou use --undo-apply-on).")
            user = self._resolve_user(opts["user"])
            if not user:
                raise CommandError(f"Usuario nao encontrado: {opts['user']!r}")
            try:
                day = dt.date.fromisoformat(opts["date"])
            except ValueError:
                raise CommandError("--date invalido; use YYYY-MM-DD")

        only_ids = None
        if opts.get("objects"):
            try:
                only_ids = [int(x) for x in opts["objects"].split(",") if x.strip()]
            except ValueError:
                raise CommandError("--objects deve ser uma lista de IDs separados por virgula")

        tz = timezone.get_default_timezone()
        start = timezone.make_aware(dt.datetime.combine(day, dt.time.min), tz)
        end = start + dt.timedelta(days=1)

        ct = ContentType.objects.get_for_model(DerivativeOperation)
        fk_fields = {f.name for f in DerivativeOperation._meta.fields if f.is_relation}

        log_filter = dict(content_type=ct, action=ACTION, created_at__gte=start, created_at__lt=end)
        if undo_mode:
            # Logs gerados pelo proprio comando ao rodar --apply (sem request user).
            log_filter["user__isnull"] = True
        else:
            log_filter["user"] = user
        if only_ids is not None:
            log_filter["object_id__in"] = only_ids

        logs = list(AuditLog.objects.filter(**log_filter).order_by("object_id", "created_at"))

        if undo_mode:
            self.stdout.write(
                f"MODO DESFAZER --apply de {day.isoformat()} "
                f"({start.isoformat()} -> {end.isoformat()}) | logs com user nulo"
            )
        else:
            self.stdout.write(
                f"Usuario: {user} (id={user.pk}) | dia {day.isoformat()} "
                f"({start.isoformat()} -> {end.isoformat()})"
            )
        if only_ids is not None:
            self.stdout.write(f"Escopo restrito aos IDs: {only_ids}")
        self.stdout.write(f"Logs 'alterado' de DerivativeOperation nesse recorte: {len(logs)}")
        if not logs:
            self.stdout.write(self.style.WARNING("Nada a fazer."))
            return

        by_obj = {}
        for log in logs:
            by_obj.setdefault(log.object_id, []).append(log)

        report = {
            "mode": "undo" if undo_mode else "revert",
            "user": str(user) if user else None,
            "user_id": user.pk if user else None,
            "date": day.isoformat(),
            "objects_filter": only_ids,
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
                        if not opts.get("include_fk"):
                            finfo["acao"] = "REVISAO MANUAL (campo de relacao/FK; use --include-fk)"
                            total_manual += 1
                            entry["fields"].append(finfo)
                            self.stdout.write(self.style.WARNING(
                                f"    - {fname}: FK alterada ({cur!r} -> deveria voltar p/ {target!r}) "
                                f"-> revisao manual (--include-fk p/ tratar)"
                            ))
                            continue
                        if _eq(mf, cur, target):
                            finfo["acao"] = "ok (FK ja esta no valor correto)"
                            total_ok += 1
                            entry["fields"].append(finfo)
                            continue
                        if not _eq(mf, cur, expected):
                            finfo["acao"] = "REVISAO MANUAL (FK atual difere do after auditado: mexido depois)"
                            total_manual += 1
                            entry["fields"].append(finfo)
                            self.stdout.write(self.style.WARNING(
                                f"    - {fname}: FK atual={cur!r} != after auditado={expected!r} "
                                f"-> mexido depois (revisao manual)"
                            ))
                            continue
                        if target is None:
                            updates[fname] = None
                            finfo["fk_resolvido"] = None
                            finfo["acao"] = "reverter FK -> None" if opts["apply"] else "reverteria FK -> None (dry-run)"
                            total_revert += 1
                            entry["fields"].append(finfo)
                            self.stdout.write(f"    - {fname}: {cur!r} -> None [FK]")
                            continue
                        matches = self._resolve_fk(mf, target)
                        if len(matches) == 1:
                            updates[fname] = matches[0]
                            finfo["fk_resolvido"] = f"{matches[0]._meta.label} id={matches[0].pk}"
                            finfo["acao"] = "reverter FK" if opts["apply"] else "reverteria FK (dry-run)"
                            total_revert += 1
                            entry["fields"].append(finfo)
                            self.stdout.write(
                                f"    - {fname}: {cur!r} -> {target!r} "
                                f"[FK -> {matches[0]._meta.label} id={matches[0].pk}]"
                            )
                        else:
                            finfo["fk_candidatos"] = [f"{m._meta.label} id={m.pk}" for m in matches]
                            finfo["acao"] = f"REVISAO MANUAL (FK '{target}': {len(matches)} candidato(s))"
                            total_manual += 1
                            entry["fields"].append(finfo)
                            self.stdout.write(self.style.ERROR(
                                f"    - {fname}: FK {target!r} -> {len(matches)} candidato(s) "
                                f"{finfo['fk_candidatos']} -> REVISAO MANUAL"
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
