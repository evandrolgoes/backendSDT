"""Gera cod_operacao_mae unico para cada DerivativeOperation com tipo_derivativo='NDF'.

NDFs sao operacoes standalone (nao multi-perna) — nao deveriam compartilhar
cod_operacao_mae. Este comando reescreve o cod_operacao_mae de TODAS as NDFs
para um codigo unico/aleatorio, rompendo qualquer agrupamento existente.

Seguro por padrao:
  - dry-run (nao grava nada) ate passar --apply;
  - tudo dentro de uma transacao (rollback automatico no dry-run);
  - cada save gera audit log (action='alterado', user=None);
  - codigos novos nao colidem com nenhum cod_operacao_mae ja existente no banco.

Reversibilidade: como cada mudanca vira um AuditLog com user=None, da pra
desfazer com `revert_derivative_edits --undo-apply-on YYYY-MM-DD --objects <ids>`.

Exemplos:
  python manage.py unique_codes_for_ndf
  python manage.py unique_codes_for_ndf --apply --report /tmp/ndf_codes.json
"""

import datetime as dt
import json
import secrets

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.derivatives.models import DerivativeOperation


def _gen_code():
    """Gera codigo no formato NDF-YYYYMMDD-HHMMSS-xxxxxxxx (timestamp + sufixo aleatorio)."""
    now = dt.datetime.now()
    suffix = secrets.token_urlsafe(6)[:8]
    return f"NDF-{now.strftime('%Y%m%d-%H%M%S')}-{suffix}"


class Command(BaseCommand):
    help = "Gera cod_operacao_mae unico para cada NDF (rompe agrupamento por cod)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="grava as mudancas (sem isso, apenas dry-run)")
        parser.add_argument(
            "--report", default=None,
            help="caminho opcional para salvar um relatorio JSON com a lista old->new",
        )

    def handle(self, *args, **opts):
        ndfs = list(
            DerivativeOperation.objects
            .filter(tipo_derivativo="NDF")
            .order_by("id")
        )
        self.stdout.write(f"NDFs encontradas: {len(ndfs)}")

        if not ndfs:
            self.stdout.write(self.style.WARNING("Nada a fazer."))
            return

        # Pool de codigos ja em uso em qualquer registro -> evita colisao.
        used_codes = set(
            DerivativeOperation.objects.values_list("cod_operacao_mae", flat=True)
        )

        changes = []
        with transaction.atomic():
            for op in ndfs:
                old_code = op.cod_operacao_mae or ""
                new_code = _gen_code()
                while new_code in used_codes:
                    new_code = _gen_code()
                used_codes.add(new_code)
                changes.append({"id": op.id, "old": old_code, "new": new_code})
                self.stdout.write(f"  obj {op.id}: {old_code!r} -> {new_code!r}")
                if opts["apply"]:
                    op.cod_operacao_mae = new_code
                    op.save(update_fields=["cod_operacao_mae"])

            self.stdout.write("")
            self.stdout.write(f"Total: {len(changes)} NDF(s) reescritas")

            if not opts["apply"]:
                self.stdout.write(self.style.WARNING(
                    "DRY-RUN: nada foi gravado. Rode com --apply para aplicar."
                ))
                transaction.set_rollback(True)
            else:
                self.stdout.write(self.style.SUCCESS("Aplicado e commitado."))

        if opts["report"]:
            with open(opts["report"], "w", encoding="utf-8") as fh:
                json.dump(
                    {
                        "datetime": dt.datetime.now().isoformat(),
                        "apply": bool(opts["apply"]),
                        "total": len(changes),
                        "changes": changes,
                    },
                    fh,
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                )
            self.stdout.write(f"Relatorio salvo em {opts['report']}")
