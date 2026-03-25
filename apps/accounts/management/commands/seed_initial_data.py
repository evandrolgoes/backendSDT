from django.core.management.base import BaseCommand

from django.contrib.auth import get_user_model
from apps.accounts.models import Role
from apps.catalog.models import Crop, Currency, DerivativeOperationName, Exchange, PriceSource, PriceUnit, Unit
from apps.clients.models import Counterparty, CropSeason, EconomicGroup, SubGroup
from apps.derivatives.models import DerivativeOperation
from apps.physical.models import ActualCost, BudgetCost, PhysicalQuote, PhysicalSale
from apps.strategies.models import CropBoard, HedgePolicy, Strategy, StrategyTrigger


class Command(BaseCommand):
    help = "Seeds initial roles, base records and demo data for the main datatypes."

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

        for nome in ["Compra Call", "Venda Put", "Venda Call", "Venda Put", "Venda NDF", "Compra NDF"]:
            DerivativeOperationName.objects.get_or_create(nome=nome)

        tenant = User.objects.filter(tenant__isnull=False).values_list("tenant", flat=True).first()
        owner = User.objects.filter(tenant_id=tenant).order_by("is_superuser", "id").last() if tenant else User.objects.first()

        if not tenant:
            self.stdout.write(
                self.style.WARNING("Nenhum tenant vinculado a usuario foi encontrado. Apenas dados globais foram carregados.")
            )
            self.stdout.write(self.style.SUCCESS("Initial data seeded successfully."))
            return

        soja = Crop.objects.get(ativo="Soja")
        milho = Crop.objects.get(ativo="Milho")

        grupo_alpha, _ = EconomicGroup.objects.get_or_create(tenant_id=tenant, grupo="Grupo Alpha")
        grupo_sertao, _ = EconomicGroup.objects.get_or_create(tenant_id=tenant, grupo="Grupo Sertao")

        subgrupo_norte, _ = SubGroup.objects.get_or_create(tenant_id=tenant, subgrupo="Fazenda Norte")
        subgrupo_sul, _ = SubGroup.objects.get_or_create(tenant_id=tenant, subgrupo="Fazenda Sul")
        subgrupo_leste, _ = SubGroup.objects.get_or_create(tenant_id=tenant, subgrupo="Unidade Leste")

        safra_2425, _ = CropSeason.objects.get_or_create(tenant_id=tenant, safra="24/25")
        safra_2526, _ = CropSeason.objects.get_or_create(tenant_id=tenant, safra="25/26")

        contraparte_a, _ = Counterparty.objects.get_or_create(
            tenant_id=tenant,
            grupo=grupo_alpha,
            subgrupo=subgrupo_norte,
            obs="Trading Aurora",
        )
        contraparte_b, _ = Counterparty.objects.get_or_create(
            tenant_id=tenant,
            grupo=grupo_sertao,
            subgrupo=subgrupo_leste,
            obs="Broker Delta",
        )

        PhysicalQuote.objects.get_or_create(
            tenant_id=tenant,
            cultura_texto="Soja",
            data_report="2026-03-10",
            defaults={
                "created_by": owner,
                "cotacao": 132.45,
                "data_pgto": "2026-03-30",
                "localidade": "Rondonopolis/MT",
                "moeda_unidade": "R$/sc",
                "safra": safra_2425,
                "obs": "Cotacao de referencia para fechamento semanal",
            },
        )
        PhysicalQuote.objects.get_or_create(
            tenant_id=tenant,
            cultura_texto="Milho",
            data_report="2026-03-11",
            defaults={
                "created_by": owner,
                "cotacao": 71.8,
                "data_pgto": "2026-04-05",
                "localidade": "Sorriso/MT",
                "moeda_unidade": "R$/sc",
                "safra": safra_2526,
                "obs": "Mercado spot interior",
            },
        )

        BudgetCost.objects.get_or_create(
            tenant_id=tenant,
            grupo=grupo_alpha,
            subgrupo=subgrupo_norte,
            cultura=soja,
            safra=safra_2425,
            grupo_despesa="Fertilizantes",
            defaults={
                "created_by": owner,
                "considerar_na_politica_de_hedge": True,
                "moeda": "R$",
                "valor": 185000.0,
                "obs": "Planejamento anual de insumos",
            },
        )
        BudgetCost.objects.get_or_create(
            tenant_id=tenant,
            grupo=grupo_sertao,
            subgrupo=subgrupo_leste,
            cultura=milho,
            safra=safra_2526,
            grupo_despesa="Diesel",
            defaults={
                "created_by": owner,
                "considerar_na_politica_de_hedge": False,
                "moeda": "R$",
                "valor": 74000.0,
                "obs": "Consumo estimado para plantio e colheita",
            },
        )

        ActualCost.objects.get_or_create(
            tenant_id=tenant,
            grupo=grupo_alpha,
            subgrupo=subgrupo_sul,
            cultura=soja,
            safra=safra_2425,
            grupo_despesa="Sementes",
            defaults={
                "created_by": owner,
                "moeda": "R$",
                "valor": 61250.0,
                "obs": "Compra realizada em fevereiro",
            },
        )
        ActualCost.objects.get_or_create(
            tenant_id=tenant,
            grupo=grupo_sertao,
            subgrupo=subgrupo_leste,
            cultura=milho,
            safra=safra_2526,
            grupo_despesa="Defensivos",
            defaults={
                "created_by": owner,
                "moeda": "R$",
                "valor": 43890.0,
                "obs": "Aplicacao prevista para abril",
            },
        )

        derivativo_put, _ = DerivativeOperation.objects.get_or_create(
            tenant_id=tenant,
            cod_operacao_mae="DRV-001",
            ordem=1,
            defaults={
                "created_by": owner,
                "grupo": grupo_alpha,
                "subgrupo": subgrupo_norte,
                "ativo": soja,
                "safra": safra_2425,
                "bolsa_ref": "CME",
                "status_operacao": "Em aberto",
                "contraparte": contraparte_a,
                "data_contratacao": "2026-03-05",
                "data_liquidacao": "2026-07-20",
                "contrato_derivativo": "PUT SOJA CME JUL26",
                "dolar_ptax_vencimento": 5.75,
                "moeda_ou_cmdtye": "Cmdtye",
                "strike_moeda_unidade": "U$/bus",
                "nome_da_operacao": "Compra Put",
                "posicao": "Compra",
                "tipo_derivativo": "Put",
                "custo_total_montagem_brl": 18250.0,
                "ajustes_totais_usd": 15200.0,
                "volume_financeiro_moeda": "U$",
                "volume_financeiro_valor": 52000.0,
                "volume_fisico_unidade": "bus",
                "volume_fisico_valor": 18000.0,
                "obs": "Protecao inicial da operacao",
            },
        )

        derivativo_ndf, _ = DerivativeOperation.objects.get_or_create(
            tenant_id=tenant,
            cod_operacao_mae="DRV-002",
            ordem=1,
            defaults={
                "created_by": owner,
                "grupo": grupo_sertao,
                "subgrupo": subgrupo_leste,
                "ativo": milho,
                "safra": safra_2526,
                "bolsa_ref": "B3",
                "status_operacao": "Em aberto",
                "contraparte": contraparte_b,
                "data_contratacao": "2026-03-08",
                "data_liquidacao": "2026-08-12",
                "contrato_derivativo": "NDF USD JUL26",
                "dolar_ptax_vencimento": 5.68,
                "moeda_ou_cmdtye": "Moeda",
                "strike_moeda_unidade": "R$/@",
                "nome_da_operacao": "Venda NDF",
                "posicao": "Venda",
                "tipo_derivativo": "NDF",
                "custo_total_montagem_brl": 9800.0,
                "ajustes_totais_usd": 8300.0,
                "volume_financeiro_moeda": "U$",
                "volume_financeiro_valor": 43000.0,
                "volume_fisico_unidade": "@",
                "volume_fisico_valor": 9500.0,
                "obs": "Estrutura principal de hedge cambial",
            },
        )
        DerivativeOperation.objects.get_or_create(
            tenant_id=tenant,
            cod_operacao_mae="DRV-002",
            ordem=2,
            defaults={
                "created_by": owner,
                "grupo": grupo_sertao,
                "subgrupo": subgrupo_leste,
                "ativo": milho,
                "safra": safra_2526,
                "bolsa_ref": "B3",
                "status_operacao": "Em aberto",
                "contraparte": contraparte_b,
                "data_contratacao": "2026-03-08",
                "data_liquidacao": "2026-08-12",
                "contrato_derivativo": "NDF USD JUL26",
                "dolar_ptax_vencimento": 5.68,
                "moeda_ou_cmdtye": "Moeda",
                "strike_moeda_unidade": "R$/@",
                "nome_da_operacao": "Venda NDF",
                "posicao": "Compra",
                "tipo_derivativo": "Call",
                "custo_total_montagem_brl": 6200.0,
                "ajustes_totais_usd": 4100.0,
                "volume_financeiro_moeda": "U$",
                "volume_financeiro_valor": 43000.0,
                "volume_fisico_unidade": "@",
                "volume_fisico_valor": 5000.0,
                "obs": "Segunda perna complementar da estrutura",
            },
        )

        estrategia, _ = Strategy.objects.get_or_create(
            tenant_id=tenant,
            descricao_estrategia="Protecao parcial da margem soja 24/25",
            defaults={
                "created_by": owner,
                "data_validade": "2026-06-30",
                "grupo": grupo_alpha,
                "subgrupo": subgrupo_norte,
                "obs": "Executar derivativo quando atingir strike alvo",
                "status": "Ativa",
            },
        )

        gatilho, _ = StrategyTrigger.objects.get_or_create(
            estrategia=estrategia,
            contrato_bolsa="SCK26",
            defaults={
                "acima_abaixo": "Acima",
                "cultura": soja,
                "codigo_derivativo": derivativo_put.cod_operacao_mae,
                "codigos_estrategia": ["EST-001"],
                "posicao": "Compra",
                "produto_bolsa": "Soja/CME",
                "status_gatilho": "nao atingido",
                "strike_alvo": 12.8,
                "tipo_fis_der": "Derivativo",
                "unidade": "bus",
                "volume": 18000.0,
                "obs": "Aguardar abertura de janela",
                "status": "Monitorando",
            },
        )
        gatilho.grupos.set([grupo_alpha])
        gatilho.subgrupos.set([subgrupo_norte])

        politica, _ = HedgePolicy.objects.get_or_create(
            tenant_id=tenant,
            cultura=soja,
            safra=safra_2425,
            mes_ano="2026-03-01",
            defaults={
                "created_by": owner,
                "insumos_travados_maximo": 65,
                "insumos_travados_minimo": 35,
                "margem_alvo_minimo": 18,
                "obs": "Faixa de politica para revisao mensal",
                "vendas_x_custo_maximo": 70,
                "vendas_x_custo_minimo": 40,
                "vendas_x_prod_total_maximo": 55,
                "vendas_x_prod_total_minimo": 25,
            },
        )
        politica.grupos.set([grupo_alpha])
        politica.subgrupos.set([subgrupo_norte, subgrupo_sul])

        quadro_safra, _ = CropBoard.objects.get_or_create(
            tenant_id=tenant,
            cultura=soja,
            safra=safra_2425,
            defaults={
                "created_by": owner,
                "area": 2480.0,
                "bolsa_ref": "CME",
                "monitorar_vc": True,
                "obs": "Talhoes mais produtivos do portfolio",
                "produtividade": 63.5,
                "producao_total": 157480.0,
                "criar_politica_hedge": True,
                "unidade_producao": "sc",
            },
        )
        quadro_safra.grupos.set([grupo_alpha])
        quadro_safra.subgrupos.set([subgrupo_norte, subgrupo_sul])

        quadro_safra_milho, _ = CropBoard.objects.get_or_create(
            tenant_id=tenant,
            cultura=milho,
            safra=safra_2526,
            defaults={
                "created_by": owner,
                "area": 1380.0,
                "bolsa_ref": "B3",
                "monitorar_vc": False,
                "obs": "Segunda safra com foco em comercializacao gradual",
                "produtividade": 108.2,
                "producao_total": 149316.0,
                "criar_politica_hedge": False,
                "unidade_producao": "sc",
            },
        )
        quadro_safra_milho.grupos.set([grupo_sertao])
        quadro_safra_milho.subgrupos.set([subgrupo_leste])

        venda_fisica, _ = PhysicalSale.objects.get_or_create(
            tenant_id=tenant,
            cultura_produto="Soja",
            defaults={
                "created_by": owner,
                "cultura": soja,
                "safra": safra_2425,
                "basis_valor": -1.2,
                "basis_moeda": "U$/bus",
                "bolsa_ref": "CME",
                "cif_fob": "FOB",
                "compra_venda": "Venda",
                "contraparte": contraparte_a,
                "cotacao_bolsa_ref": 12.9,
                "cultura_produto": "Soja",
                "data_entrega": "2026-04-20",
                "data_negociacao": "2026-03-12",
                "data_pagamento": "2026-04-25",
                "dolar_de_venda": 5.77,
                "moeda_contrato": "R$",
                "objetivo_venda_dolarizada": "Protecao da margem",
                "pf_paf": "PF",
                "preco": 131.8,
                "unidade_contrato": "sc",
                "volume_fisico": 8450.0,
            },
        )
        venda_fisica.grupos.set([grupo_alpha])
        venda_fisica.subgrupos.set([subgrupo_norte])

        venda_fisica_milho, _ = PhysicalSale.objects.get_or_create(
            tenant_id=tenant,
            cultura_produto="Milho",
            defaults={
                "created_by": owner,
                "cultura": milho,
                "safra": safra_2526,
                "basis_valor": -0.45,
                "basis_moeda": "R$/sc",
                "bolsa_ref": "B3",
                "cif_fob": "CIF",
                "compra_venda": "Venda",
                "contraparte": contraparte_b,
                "cotacao_bolsa_ref": 72.1,
                "cultura_produto": "Milho",
                "data_entrega": "2026-08-10",
                "data_negociacao": "2026-03-14",
                "data_pagamento": "2026-08-18",
                "dolar_de_venda": 5.7,
                "moeda_contrato": "R$",
                "objetivo_venda_dolarizada": "Caixa de safra",
                "pf_paf": "PAF",
                "preco": 70.9,
                "unidade_contrato": "sc",
                "volume_fisico": 9620.0,
            },
        )
        venda_fisica_milho.grupos.set([grupo_sertao])
        venda_fisica_milho.subgrupos.set([subgrupo_leste])

        self.stdout.write(self.style.SUCCESS("Initial data seeded successfully."))
