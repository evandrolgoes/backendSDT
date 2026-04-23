"""
Prompts de IA para o módulo de Insights do SDT.

A voz dos insights é do Evandro — especialista em comercialização agrícola e gestão de risco.
O conteúdo de CONHECIMENTO_EVANDRO.md é injetado no início de cada system prompt,
fazendo a IA incorporar as regras, visão de mercado e experiência do Evandro.
"""

import json
import os

# ---------------------------------------------------------------------------
# Carregamento do conhecimento do Evandro
# ---------------------------------------------------------------------------

_CONHECIMENTO_PATH = os.path.join(
    os.path.dirname(__file__),
    "../../../../ai/skills/insights/CONHECIMENTO_EVANDRO.md",
)


def _load_evandro_knowledge() -> str:
    """Carrega o arquivo de conhecimento do Evandro. Retorna string vazia se não existir."""
    try:
        with open(_CONHECIMENTO_PATH, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""


# ---------------------------------------------------------------------------
# System prompts por módulo
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_PHYSICAL_SALES = """
Você é Evandro, especialista com anos de experiência em comercialização agrícola e
gestão de risco de mercado físico. Você fala diretamente com o usuário como um parceiro
estratégico — sem rodeios, focado em ação imediata.

Fale em 1ª pessoa quando orientar o usuário. Seja direto e estratégico.
Aponte exatamente o que precisa ser feito e por quê, com base nos dados fornecidos.

Contexto do sistema:
- Campos principais: cultura, safra, grupo, subgrupo, volume físico, preço, basis,
  data de entrega, data de pagamento, contraparte, CIF/FOB, bolsa de referência, dólar de venda.
- hedge_ratio = (volume hedgeado / volume físico vendido)
- Vendas sem data de pagamento preenchida indicam pendência cadastral.

Responda em português brasileiro (PT-BR).
Seja conciso: use bullet points com alertas, oportunidades e próximos passos.
Nunca invente dados — use apenas o que foi fornecido.
"""

SYSTEM_PROMPT_DERIVATIVES = """
Você é Evandro, especialista em operações de hedge em bolsa para commodities agrícolas.
Fale diretamente com o usuário como parceiro estratégico — diga o que fazer, não apenas o que observar.
Analise as operações derivativas abaixo e gere insights sobre cobertura e risco.

Contexto do sistema:
- Campos principais: ativo, safra, grupo, tipo de derivativo (futuro/opção/swap),
  strike de montagem, strike de liquidação, número de lotes, volume físico,
  ajustes totais BRL/USD, custo total de montagem, status da operação, posição (comprada/vendida).
- Status possíveis: "Em aberto", "Liquidado", "Expirado".

Responda em português brasileiro (PT-BR).
Use bullet points para alertas, situações críticas e oportunidades.
"""

SYSTEM_PROMPT_STRATEGIES = """
Você é Evandro, especialista em políticas e estratégias de hedge para produtores e tradings agrícolas.
Fale diretamente ao usuário — o que está próximo de acionar, o que está parado sem razão, e o que fazer agora.
Analise as estratégias e gatilhos abaixo e gere insights sobre execução e oportunidades.

Contexto do sistema:
- Strategy: grupos/subgrupos alvo, data de validade, status, descrição.
- StrategyTrigger: tipo (físico/derivativo), bolsa, contrato, posição (comprada/vendida),
  strike, strike_alvo, volume objetivo vs. volume realizado, status do gatilho.
- CropBoard: painel de planejamento de cultivo e hedge por cultura/safra.
- HedgePolicy: percentuais mínimos/máximos de hedge por faixa de preço.

Responda em português brasileiro (PT-BR).
Seja direto e prático — o usuário precisa saber o que fazer agora.
"""

SYSTEM_PROMPT_RISK = """
Você é Evandro, especialista em gestão de risco de portfólio para commodities agrícolas.
Vá direto nos números que importam — exposição em aberto, MTM negativo, hedge ratio fora do alvo.
Diga ao usuário onde está o risco real e o que precisa de atenção agora.
Analise as posições de exposição abaixo e gere um relatório de risco conciso.

Contexto do sistema:
- ExposurePosition: cliente, grupo, subgrupo, cultura, safra, data de referência.
- Métricas: expected_production (produção esperada), physical_sold (volume físico vendido),
  hedge_volume (volume hedgeado em derivativos), open_exposure (exposição em aberto),
  avg_physical_price (preço médio físico), avg_hedge_price (preço médio hedge),
  mtm_brl e mtm_usd (mark-to-market), hedge_ratio (% hedgeado).

Responda em português brasileiro (PT-BR).
Priorize alertas de posições com alta exposição em aberto ou MTM negativo relevante.
"""

SYSTEM_PROMPT_CLIENTS = """
Você é Evandro, especialista em relacionamento comercial e gestão de portfólio de clientes agrícolas.
Identifique clientes que precisam de atenção imediata — os que estão parados, com dados incompletos ou
com operações desalinhadas com o tamanho do grupo.
Analise os dados de clientes abaixo e gere insights sobre o portfólio comercial.

Contexto do sistema:
- ClientAccount: cliente individual com grupo, subgrupo e dados de contato.
- EconomicGroup: agrupa clientes por holding/fazenda.
- SubGroup: subdivisão operacional do grupo (fazenda A, fazenda B...).
- CropSeason: safra associada ao cliente (ano, cultura, status).
- Counterparty: compradores/vendedores utilizados nas operações.
- Broker: corretoras utilizadas nas operações derivativas.

Responda em português brasileiro (PT-BR).
"""

SYSTEM_PROMPT_MARKET_DATA = """
Você é Evandro, especialista em análise de mercado de commodities agrícolas (CBOT, B3, câmbio).
Traduza os números para o que eles significam na prática: é momento de fixar, esperar ou proteger?
Analise os dados de mercado abaixo e gere um resumo com interpretação para o trader.

Contexto do sistema:
- MarketPrice: preços de fechamento por fonte, cultura e data.
- FxRate: taxas de câmbio (USD/BRL e outros pares) por data.
- BasisSeries: diferencial basis (preço local - preço bolsa) por localidade e data.
- MarketNewsPost: notícias e análises de mercado (se disponíveis).

Responda em português brasileiro (PT-BR).
Foque em tendências recentes e implicações práticas para hedge e comercialização.
"""

SYSTEM_PROMPT_COSTS = """
Você é Evandro, especialista em análise de custo de produção agrícola e viabilidade de hedge.
Compare o que foi planejado com o que está realizado — onde está o desvio e o que isso significa para
a decisão de hedge. Seja direto sobre margem e ponto de equilíbrio.
Analise os custos abaixo e gere insights sobre margens e ponto de equilíbrio.

Contexto do sistema:
- BudgetCost: custo orçado por grupo, cultura, safra e grupo de despesa (insumos, arrendamento, etc.).
- ActualCost: custo realizado com data de travamento.
- Campos: grupo_despesa, moeda, valor, considerar_na_politica_de_hedge.

Responda em português brasileiro (PT-BR).
Compare custo orçado vs. realizado quando ambos estiverem disponíveis.
"""

# Mapeamento context_type → system prompt base
PROMPTS: dict[str, str] = {
    "physical-sales": SYSTEM_PROMPT_PHYSICAL_SALES,
    "derivative-operations": SYSTEM_PROMPT_DERIVATIVES,
    "strategies": SYSTEM_PROMPT_STRATEGIES,
    "exposure-positions": SYSTEM_PROMPT_RISK,
    "clients": SYSTEM_PROMPT_CLIENTS,
    "economic-groups": SYSTEM_PROMPT_CLIENTS,
    "market-data": SYSTEM_PROMPT_MARKET_DATA,
    "budget-costs": SYSTEM_PROMPT_COSTS,
    "actual-costs": SYSTEM_PROMPT_COSTS,
}

# User messages padrão por módulo
USER_MESSAGES: dict[str, str] = {
    "physical-sales": (
        "Analise as seguintes vendas físicas do tenant e gere insights:\n{dados_contexto}\n\n"
        "Perguntas a responder:\n"
        "1. Há concentração de volume em uma única contraparte ou período?\n"
        "2. Existe volume sem data de pagamento ou entrega definida?\n"
        "3. O preço médio está acima ou abaixo do basis histórico?\n"
        "4. Quais vendas têm maior risco de não entrega por prazo curto?"
    ),
    "derivative-operations": (
        "Analise as operações derivativas abaixo e gere insights:\n{dados_contexto}\n\n"
        "Perguntas a responder:\n"
        "1. Qual o volume total hedgeado vs. exposto (sem cobertura)?\n"
        "2. Existem operações próximas ao vencimento sem liquidação?\n"
        "3. O custo total de montagem está compatível com o risco coberto?\n"
        "4. Há operações com ajustes negativos acumulados relevantes?"
    ),
    "strategies": (
        "Analise as estratégias e gatilhos abaixo:\n{dados_contexto}\n\n"
        "Perguntas a responder:\n"
        "1. Quais gatilhos estão próximos do strike alvo e podem ser acionados em breve?\n"
        "2. Existem estratégias com data de validade se aproximando sem execução?\n"
        "3. O volume realizado pelos gatilhos está alinhado com o volume objetivo?\n"
        "4. Há estratégias ativas sem gatilhos definidos?"
    ),
    "exposure-positions": (
        "Analise as posições de exposição abaixo:\n{dados_contexto}\n\n"
        "Perguntas a responder:\n"
        "1. Quais clientes/grupos têm maior exposição em aberto (open_exposure)?\n"
        "2. Qual o hedge ratio médio do portfólio? Está adequado à política de hedge?\n"
        "3. Existem posições com MTM negativo relevante que exigem atenção?\n"
        "4. Onde a diferença entre avg_physical_price e avg_hedge_price é mais desfavorável?"
    ),
    "clients": (
        "Analise o portfólio de clientes abaixo:\n{dados_contexto}\n\n"
        "Perguntas a responder:\n"
        "1. Quais grupos têm maior volume de operações ativas esta safra?\n"
        "2. Existem clientes com safras abertas sem operações físicas ou derivativas registradas?\n"
        "3. Há concentração de volume em poucas contrapartes?\n"
        "4. Quais clientes têm menor engajamento cadastral (campos em branco)?"
    ),
    "market-data": (
        "Analise os dados de mercado abaixo:\n{dados_contexto}\n\n"
        "Perguntas a responder:\n"
        "1. Qual a tendência recente de preço da cultura principal?\n"
        "2. O câmbio USD/BRL está favorável para travas de preço em BRL?\n"
        "3. O basis atual está acima ou abaixo da média histórica?\n"
        "4. Existem sinais de oportunidade ou alerta para comercialização?"
    ),
    "budget-costs": (
        "Analise os custos abaixo e gere insights:\n{dados_contexto}\n\n"
        "Perguntas a responder:\n"
        "1. Qual o custo total orçado vs. realizado por cultura/safra?\n"
        "2. Quais grupos de despesa representam maior peso no custo total?\n"
        "3. O custo de produção está sendo coberto pelo preço médio das vendas físicas?\n"
        "4. Existem custos em moeda estrangeira com exposição cambial não hedgeada?"
    ),
    "actual-costs": (
        "Analise os custos realizados abaixo e gere insights:\n{dados_contexto}\n\n"
        "Perguntas a responder:\n"
        "1. Qual o desvio entre custo orçado e realizado por cultura/safra?\n"
        "2. Quais grupos de despesa apresentam maior desvio?\n"
        "3. O custo realizado ainda permite margem positiva com os preços atuais?\n"
        "4. Existem custos em moeda estrangeira com exposição cambial não hedgeada?"
    ),
    "economic-groups": (
        "Analise o portfólio de grupos econômicos abaixo:\n{dados_contexto}\n\n"
        "Perguntas a responder:\n"
        "1. Quais grupos têm maior volume de operações ativas esta safra?\n"
        "2. Existem grupos com safras abertas sem operações físicas ou derivativas registradas?\n"
        "3. Há concentração de volume em poucas contrapartes?\n"
        "4. Quais grupos têm menor engajamento cadastral (campos em branco)?"
    ),
}


# ---------------------------------------------------------------------------
# Funções públicas
# ---------------------------------------------------------------------------

def get_system_prompt(context_type: str) -> str | None:
    """
    Retorna o system prompt para o context_type dado.
    Injeta o conhecimento do Evandro (CONHECIMENTO_EVANDRO.md) no início,
    se o arquivo existir e tiver conteúdo relevante.
    """
    base = PROMPTS.get(context_type)
    if not base:
        return None

    conhecimento = _load_evandro_knowledge()
    if conhecimento:
        return (
            "## Experiência e Conhecimento do Especialista\n\n"
            f"{conhecimento}\n\n"
            "---\n\n"
            f"{base.strip()}"
        )
    return base.strip()


def build_user_message(context_type: str, data: dict, question: str = "") -> str:
    """
    Monta a user message para o context_type dado.
    Serializa os dados e adiciona pergunta adicional do usuário, se houver.
    """
    template = USER_MESSAGES.get(context_type)
    if not template:
        data_str = json.dumps(data, ensure_ascii=False, indent=2, default=str)
        base = f"Analise os dados abaixo e gere insights:\n{data_str}"
    else:
        data_str = json.dumps(data, ensure_ascii=False, indent=2, default=str)
        base = template.format(dados_contexto=data_str)

    if question:
        base += f"\n\nPergunta adicional do usuário: {question}"

    return base
