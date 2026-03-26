from django.core.management.base import BaseCommand

from django.contrib.auth import get_user_model
from apps.accounts.models import Role
from apps.catalog.models import Crop, Currency, DerivativeOperationName, Exchange, PriceSource, PriceUnit, Unit
from apps.clients.models import CropSeason, EconomicGroup, SubGroup


class Command(BaseCommand):
    help = "Seeds initial roles and safe base records for the main datatypes."

    def handle(self, *args, **options):
        User = get_user_model()

        for code, name in [("admin", "Administrador"), ("risk_manager", "Gestor de Risco"), ("trader", "Trader"), ("viewer", "Leitor")]:
            Role.objects.get_or_create(code=code, defaults={"name": name})

        for ativo in ["Soja", "Milho", "Algodao", "Cafe"]:
            Crop.objects.get_or_create(ativo=ativo)

        for name in ["B3", "CME", "Reuters", "Manual"]:
            PriceSource.objects.get_or_create(name=name)

        for nome in ["R$", "U$", "E$"]:
            Currency.objects.get_or_create(nome=nome)

        for nome in ["sc", "bus", "@"]:
            Unit.objects.get_or_create(nome=nome)

        for nome in ["R$/sc", "U$/bus", "R$/@", "U$/sc"]:
            PriceUnit.objects.get_or_create(nome=nome)

        for nome in ["B3", "CME"]:
            Exchange.objects.get_or_create(nome=nome)

        for nome in ["Compra Call", "Venda Put", "Venda Call", "Venda NDF", "Compra NDF"]:
            DerivativeOperationName.objects.get_or_create(nome=nome)

        tenant = User.objects.filter(tenant__isnull=False).values_list("tenant", flat=True).first()
        if not tenant:
            self.stdout.write(
                self.style.WARNING("Nenhum tenant vinculado a usuario foi encontrado. Apenas dados globais foram carregados.")
            )
            self.stdout.write(self.style.SUCCESS("Initial data seeded successfully."))
            return

        grupo_alpha, _ = EconomicGroup.objects.get_or_create(tenant_id=tenant, grupo="Grupo Alpha")
        grupo_sertao, _ = EconomicGroup.objects.get_or_create(tenant_id=tenant, grupo="Grupo Sertao")

        subgrupo_norte, _ = SubGroup.objects.get_or_create(tenant_id=tenant, subgrupo="Fazenda Norte")
        subgrupo_sul, _ = SubGroup.objects.get_or_create(tenant_id=tenant, subgrupo="Fazenda Sul")
        subgrupo_leste, _ = SubGroup.objects.get_or_create(tenant_id=tenant, subgrupo="Unidade Leste")

        safra_2425, _ = CropSeason.objects.get_or_create(tenant_id=tenant, safra="24/25")
        safra_2526, _ = CropSeason.objects.get_or_create(tenant_id=tenant, safra="25/26")

        self.stdout.write(self.style.SUCCESS("Initial data seeded successfully."))
