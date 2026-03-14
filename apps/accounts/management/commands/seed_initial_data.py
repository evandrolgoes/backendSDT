from django.core.management.base import BaseCommand

from apps.accounts.models import Role
from apps.catalog.models import Crop, PriceSource, UnitOfMeasure


class Command(BaseCommand):
    help = "Seeds initial roles, crops, units and price sources."

    def handle(self, *args, **options):
        for code, name in [("admin", "Administrador"), ("risk_manager", "Gestor de Risco"), ("trader", "Trader"), ("viewer", "Leitor")]:
            Role.objects.get_or_create(code=code, defaults={"name": name})

        for code, name in [("SOY", "Soja"), ("CORN", "Milho"), ("COT", "Algodão"), ("COF", "Café")]:
            Crop.objects.get_or_create(code=code, defaults={"name": name})

        for code, name, factor in [("KG", "Quilograma", "1"), ("SC60", "Saca 60kg", "60"), ("TON", "Tonelada", "1000"), ("LB", "Libra", "0.453592")]:
            UnitOfMeasure.objects.get_or_create(code=code, defaults={"name": name, "conversion_to_kg": factor})

        for name in ["B3", "CME", "Reuters", "Manual"]:
            PriceSource.objects.get_or_create(name=name)

        self.stdout.write(self.style.SUCCESS("Initial data seeded successfully."))
