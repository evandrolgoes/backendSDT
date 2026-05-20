"""Desfaz alteracoes de DerivativeOperation feitas por um usuario num dia.

Usa a trilha de auditoria (apps.auditing.AuditLog). Para cada objeto tocado
pelo usuario no dia (alterado/criado/excluido), calcula o efeito-liquido e
aplica o caminho correto, num unico passo:

  Caso A — existia antes e existe agora -> RESTAURAR (campo a campo p/ before)
  Caso B — existia antes, nao existe agora (foi deletado) -> RECRIAR com PK
           original + FK resolvidos (requer --include-fk; ambiguos = bloqueado)
  Caso C — nao existia antes, existe agora (foi criado hoje) -> DELETAR
  Caso D — nao existia antes e nao existe agora -> NADA (criado e deletado)

Seguro por padrao:
  - dry-run (nao grava nada) ate passar --apply;
  - safety check (campo difere do after auditado -> mexido depois -> manual);
  - FK ambiguo/nao encontrado vira "BLOQUEADO" (nada e gravado);
  - idempotente (RESTORE pula campos ja no valor correto);
  - tudo dentro de uma transacao;
  - apos RECRIAR, ressincroniza a sequence de id (Postgres).

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

ACTIONS = ("alterado", "criado", "excluido")


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

        log_filter = dict(content_type=ct, action__in=ACTIONS, created_at__gte=start, created_at__lt=end)
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
        self.stdout.write(f"Logs de DerivativeOperation nesse recorte: {len(logs)} (alterado/criado/excluido)")
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
        total_recreated = total_deleted = total_blocked = total_nothing = 0
        recreated_any = False

        with transaction.atomic():
            for object_id, obj_logs in by_obj.items():
                obj = DerivativeOperation.objects.filter(pk=object_id).select_for_update().first()
                first_log = obj_logs[0]
                last_log = obj_logs[-1]
                actions_seq = [lg.action for lg in obj_logs]
                # pre_state = estado pre-dia do objeto. None se foi criado hoje
                # (nao existia antes); senao, o `before` do primeiro log do dia.
                pre_state = None if first_log.action == "criado" else first_log.changes_json.get("before", {})
                first_before = pre_state or {}
                last_after = last_log.changes_json.get("after", {})

                entry = {
                    "object_id": object_id,
                    "cod_operacao_mae": (first_before.get("cod_operacao_mae") if obj is None else obj.cod_operacao_mae),
                    "edits_no_dia": len(obj_logs),
                    "actions_today": actions_seq,
                    "fields": [],
                }

                self.stdout.write(
                    f"  obj {object_id} ({entry['cod_operacao_mae'] or '-'}): "
                    f"{len(obj_logs)} log(s) acoes={actions_seq}"
                )

                # Caso D: nao existia antes e nao existe agora -> NADA
                if pre_state is None and obj is None:
                    entry["status"] = "NADA (criado e ja deletado no mesmo dia)"
                    total_nothing += 1
                    self.stdout.write("    -> NADA (criado e ja deletado)")
                    report["objects"].append(entry)
                    continue

                # Caso C: nao existia antes, existe agora -> DELETAR (foi criado hoje)
                if pre_state is None and obj is not None:
                    snap = serialize_instance_for_log(obj)
                    entry["status"] = "DELETADO" if opts["apply"] else "DELETARIA (dry-run)"
                    entry["snapshot_antes_delete"] = snap
                    total_deleted += 1
                    self.stdout.write(self.style.WARNING(
                        f"    -> DELETAR (criado hoje); snapshot: "
                        f"cod={snap.get('cod_operacao_mae')!r} nome={snap.get('nome_da_operacao')!r} "
                        f"ativo={snap.get('ativo')!r} contrato={snap.get('contrato_derivativo')!r}"
                    ))
                    if opts["apply"]:
                        obj.delete()
                    report["objects"].append(entry)
                    continue

                # Caso B: existia antes, nao existe agora -> RECRIAR com PK original
                if pre_state is not None and obj is None:
                    if not opts.get("include_fk"):
                        entry["status"] = "BLOQUEADO (precisa --include-fk para recriar)"
                        total_blocked += 1
                        self.stdout.write(self.style.ERROR(
                            "    -> RECRIAR requer --include-fk (FK auditados sao texto)"
                        ))
                        report["objects"].append(entry)
                        continue

                    model_field_names = {f.name for f in DerivativeOperation._meta.fields}
                    prepared = {}
                    blockers = []
                    for fname, value in pre_state.items():
                        if fname == "id" or fname not in model_field_names:
                            continue
                        mf = DerivativeOperation._meta.get_field(fname)
                        if fname in fk_fields:
                            if value is None:
                                prepared[fname] = None
                                continue
                            matches = self._resolve_fk(mf, value)
                            if len(matches) == 1:
                                prepared[fname] = matches[0]
                            else:
                                blockers.append({
                                    "campo": fname, "texto": value,
                                    "candidatos": [f"{m._meta.label} id={m.pk}" for m in matches],
                                })
                        else:
                            prepared[fname] = _coerce(mf, value)

                    if blockers:
                        entry["status"] = "BLOQUEADO (FK ambiguo/nao encontrado)"
                        entry["fk_bloqueados"] = blockers
                        total_blocked += 1
                        self.stdout.write(self.style.ERROR(f"    -> RECRIAR BLOQUEADO; FK: {blockers}"))
                        report["objects"].append(entry)
                        continue

                    field_lines = []
                    for k in sorted(prepared.keys()):
                        v = prepared[k]
                        if hasattr(v, "_meta"):
                            field_lines.append({"campo": k, "valor": f"[FK] {v._meta.label} id={v.pk}"})
                            self.stdout.write(f"      {k} = [FK] {v._meta.label} id={v.pk}")
                        else:
                            display = v.isoformat() if hasattr(v, "isoformat") else (str(v) if isinstance(v, Decimal) else v)
                            field_lines.append({"campo": k, "valor": display})
                            self.stdout.write(f"      {k} = {v!r}")
                    entry["fields"] = field_lines
                    entry["status"] = "RECRIADO" if opts["apply"] else "RECRIARIA (dry-run)"
                    total_recreated += 1

                    if opts["apply"]:
                        new_obj = DerivativeOperation(pk=object_id)
                        for k, v in prepared.items():
                            setattr(new_obj, k, v)
                        new_obj.save(force_insert=True)
                        recreated_any = True

                    report["objects"].append(entry)
                    continue

                # Caso A: existia antes e existe agora -> RESTORE (logica original)
                changed_fields = sorted({
                    c["campo"] for lg in obj_logs for c in lg.changes_json.get("changes", [])
                })
                current = serialize_instance_for_log(obj)
                updates = {}

                self.stdout.write(
                    f"    -> RESTORE; campos a checar: {', '.join(changed_fields) or '-'}"
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

            # Apos RECRIAR registros com PK explicito, ressincronizar a sequence
            # do Postgres (senao o proximo INSERT autoincrementado colide).
            if opts["apply"] and recreated_any:
                from django.db import connection
                if connection.vendor == "postgresql":
                    table = DerivativeOperation._meta.db_table
                    with connection.cursor() as cur:
                        cur.execute(
                            "SELECT setval(pg_get_serial_sequence(%s, 'id'), "
                            f"COALESCE((SELECT MAX(id) FROM {table}), 0))",
                            [table],
                        )
                    self.stdout.write("Sequence de id ressincronizada apos recriacoes.")

            self.stdout.write("")
            self.stdout.write(
                f"Resumo: {len(by_obj)} objeto(s) | "
                f"RESTORE campos: {total_revert} (ja ok {total_ok}, manual {total_manual}, sumidos {total_missing}) | "
                f"RECRIADOS: {total_recreated} | DELETADOS: {total_deleted} | "
                f"BLOQUEADOS: {total_blocked} | NADA: {total_nothing}"
            )

            if not opts["apply"]:
                self.stdout.write(self.style.WARNING(
                    "DRY-RUN: nada foi gravado. Rode de novo com --apply para aplicar."
                ))
                # Garante que um dry-run nunca persista nada.
                transaction.set_rollback(True)
            else:
                self.stdout.write(self.style.SUCCESS("Acoes aplicadas e commitadas."))

        if opts["report"]:
            with open(opts["report"], "w", encoding="utf-8") as fh:
                json.dump(report, fh, ensure_ascii=False, indent=2, default=str)
            self.stdout.write(f"Relatorio salvo em {opts['report']}")
