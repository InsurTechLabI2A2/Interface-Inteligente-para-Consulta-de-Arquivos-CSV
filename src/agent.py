from __future__ import annotations

"""Query agents: a deterministic offline agent and an optional LangChain agent."""

import os
import re
import unicodedata
from dataclasses import dataclass

import pandas as pd

from .data_engine import execute_plan, money, number
from .models import Aggregation, OrderBy, QueryPlan


def norm(value: str) -> str:
    value = unicodedata.normalize("NFD", str(value).casefold())
    return "".join(char for char in value if unicodedata.category(char) != "Mn")


def find_column(columns: list[str], *phrases: str) -> str | None:
    normalized = {column: norm(column) for column in columns}
    for phrase in phrases:
        target = norm(phrase)
        for column, normalized_column in normalized.items():
            if target == normalized_column or target in normalized_column:
                return column
    return None


def pick_table(question: str, tables: dict[str, pd.DataFrame]) -> str:
    q = norm(question)
    scored: list[tuple[int, str]] = []
    for name, frame in tables.items():
        columns = [str(column) for column in frame.columns]
        score = 0
        cols = " ".join(norm(column) for column in columns)
        if any(term in q for term in ("quantidade", "produto", "item", "ncm", "cfop")):
            score += 6 if any(term in cols for term in ("quantidade", "ncm", "cfop", "produto")) else 0
        if any(term in q for term in ("nota fiscal", "nota", "emitente", "destinatario", "uf")):
            score += 5 if any(term in cols for term in ("valor nota fiscal", "chave de acesso", "emitente", "destinatario")) else 0
        if "valor nota fiscal" in cols:
            score += 2
        scored.append((score, name))
    return max(scored)[1]


def value_column(columns: list[str], question: str, table: pd.DataFrame) -> str | None:
    q = norm(question)
    if any(term in q for term in ("quantidade", "qtd", "unidades")) and "valor" not in q:
        return find_column(columns, "QUANTIDADE", "QTD", "QUANT")
    if any(term in q for term in ("valor", "total", "preco", "preço", "gasto")):
        return find_column(columns, "VALOR NOTA FISCAL", "VALOR TOTAL", "VALOR", "TOTAL")
    return None


def group_column(columns: list[str], question: str) -> str | None:
    q = norm(question)
    if re.search(r"uf.{0,20}emitente|emitente.{0,20}uf", q):
        return find_column(columns, "UF EMITENTE")
    if re.search(r"uf.{0,20}destinat|destinat.{0,20}uf", q):
        return find_column(columns, "UF DESTINATARIO", "UF DESTINO")
    if "cfop" in q:
        return find_column(columns, "CFOP")
    if "ncm" in q:
        return find_column(columns, "CODIGO NCM/SH", "NCM/SH", "NCM")
    if "natureza" in q:
        return find_column(columns, "NATUREZA DA OPERACAO", "NATUREZA")
    if "municipio" in q or "cidade" in q:
        if "destinat" in q:
            return find_column(columns, "MUNICIPIO DESTINATARIO", "MUNICIPIO DESTINO")
        return find_column(columns, "MUNICIPIO EMITENTE", "MUNICIPIO")
    if "consumidor final" in q:
        return find_column(columns, "CONSUMIDOR FINAL")
    if any(term in q for term in ("emitente", "fornecedor", "empresa que vendeu")):
        return find_column(columns, "RAZAO SOCIAL EMITENTE", "NOME EMITENTE", "EMITENTE", "FORNECEDOR")
    if "destinat" in q:
        return find_column(columns, "NOME DESTINATARIO", "DESTINATARIO")
    if any(term in q for term in ("produto", "mercadoria")):
        return find_column(columns, "DESCRICAO DO PRODUTO", "PRODUTO")
    if "mes" in q or "mensal" in q:
        return "__MES__"
    return None


def invoice_key(columns: list[str]) -> str | None:
    return find_column(columns, "CHAVE DE ACESSO", "CHAVE NFE", "NUMERO NOTA FISCAL", "NUMERO")


@dataclass
class AgentAnswer:
    text: str
    data: pd.DataFrame
    plan: QueryPlan
    agent_name: str


class LocalCsvAgent:
    name = "Agente local determinístico"

    def plan(self, question: str, tables: dict[str, pd.DataFrame]) -> QueryPlan:
        if not tables:
            raise ValueError("Nenhuma tabela foi carregada.")
        table_name = pick_table(question, tables)
        frame = tables[table_name]
        columns = [str(column) for column in frame.columns]
        q = norm(question)
        key_col = invoice_key(columns)
        group = group_column(columns, question)
        metric = value_column(columns, question, frame)
        is_average = "media" in q or "média" in question.casefold()
        is_count = any(term in q for term in ("quantas notas", "numero de notas", "número de notas", "notas por", "mais frequente", "frequencia", "frequência", "distribuicao", "distribuição"))
        is_quantity = "quantidade" in q and not any(term in q for term in ("quantas notas", "numero de notas", "número de notas"))
        is_listing = any(term in q for term in ("liste", "listar", "mostre", "exiba"))

        if is_quantity:
            metric = find_column(columns, "QUANTIDADE", "QTD", "QUANT") or metric
        if is_count and key_col and not is_quantity:
            metric = None

        explicit_limit = re.search(r"(?:top|cinco|5|dez|10|vinte|20)\s*(?:de|dos|das)?\s*(\d+)?", q)
        numbers = [int(value) for value in re.findall(r"\b(?:\d+)\b", q)]
        if numbers:
            limit = numbers[-1]
        elif "cinco" in q:
            limit = 5
        elif "dez" in q:
            limit = 10
        elif any(term in q for term in ("maior", "menor", "mais frequente", "mais recebeu", "recebeu mais")):
            limit = 1
        else:
            limit = 10

        # A ranking of invoices is a row-level query, not a grouped query.
        ranking_rows = is_listing and ("nota" in q or "invoice" in q) and metric is not None
        if ranking_rows:
            selected: list[str] = []
            for column in (key_col, metric, find_column(columns, "DATA EMISSAO", "EMISSAO"), find_column(columns, "RAZAO SOCIAL EMITENTE", "EMITENTE")):
                if column and column not in selected:
                    selected.append(column)
            return QueryPlan(
                table=table_name,
                select=selected,
                order_by=OrderBy(column=metric, descending=True),
                limit=limit,
                output_type="table",
                explanation="Seleção das notas e ordenação pelo valor informado.",
            )

        if group == "__MES__":
            group_by = ["__MES__"]
        else:
            group_by = [group] if group else []

        aggregations: list[Aggregation] = []
        if is_average and metric:
            aggregations = [Aggregation(function="avg", column=metric, alias=f"Média de {metric}")]
        elif is_count or (group and not metric):
            count_column = key_col if key_col and "nota" in q and "cfop" not in q and "ncm" not in q else "*"
            function = "count_distinct" if count_column != "*" else "count"
            aggregations = [Aggregation(function=function, column=count_column, alias="Quantidade")]
        elif metric:
            aggregations = [Aggregation(function="sum", column=metric, alias=metric)]
        else:
            aggregations = [Aggregation(function="count", column="*", alias="Quantidade")]

        order_alias = aggregations[0].alias
        if group and any(term in q for term in ("maior", "top", "mais", "frequente", "ranking", "recebeu")):
            order = OrderBy(column=order_alias, descending=True)
        elif group:
            order = OrderBy(column=order_alias, descending=True)
        else:
            order = None
        output_type = "chart" if group and not is_listing else "table"
        if group and any(term in q for term in ("top", "liste", "listar", "maior", "mais frequente")):
            output_type = "table"
        ranking_requested = bool(numbers) or any(
            term in q for term in ("top", "maior", "menor", "mais frequente", "ranking", "recebeu mais")
        )
        group_limit = limit if ranking_requested else None
        return QueryPlan(
            table=table_name,
            group_by=group_by,
            aggregations=aggregations,
            order_by=order,
            limit=group_limit if group else None,
            output_type=output_type,
            chart_type="bar" if group else None,
            explanation="Plano local baseado no vocabulário da pergunta e no dicionário de colunas.",
        )

    def answer(self, question: str, tables: dict[str, pd.DataFrame]) -> AgentAnswer:
        plan = self.plan(question, tables)
        result = execute_plan(plan, tables)
        return AgentAnswer(format_answer(question, plan, result), result, plan, self.name)


class LangChainCsvAgent(LocalCsvAgent):
    """Optional LangChain structured-output agent; falls back safely when unavailable."""

    name = "Agente LangChain (com fallback local)"

    def __init__(self) -> None:
        self.model_name = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")

    def plan(self, question: str, tables: dict[str, pd.DataFrame]) -> QueryPlan:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            return super().plan(question, tables)
        try:
            from langchain.agents import create_agent
            from langchain_anthropic import ChatAnthropic

            schema = "\n".join(
                f"Tabela {name}: {', '.join(map(str, frame.columns))}" for name, frame in tables.items()
            )
            model = ChatAnthropic(model=self.model_name, temperature=0, api_key=api_key)
            agent = create_agent(
                model=model,
                tools=[],
                response_format=QueryPlan,
                system=(
                    "Você transforma perguntas em português em planos JSON para consultar tabelas CSV. "
                    "Use somente tabelas e colunas do esquema. Não invente dados. "
                    "Se a pergunta pedir contagem de notas, prefira count_distinct da chave de acesso.\n\n"
                    f"Esquema:\n{schema}"
                ),
            )
            response = agent.invoke({"messages": [{"role": "user", "content": question}]})
            structured = response.get("structured_response")
            if structured is None:
                return super().plan(question, tables)
            plan = structured if isinstance(structured, QueryPlan) else QueryPlan.model_validate(structured)
            if plan.table not in tables:
                return super().plan(question, tables)
            return plan
        except Exception:
            return super().plan(question, tables)

    def answer(self, question: str, tables: dict[str, pd.DataFrame]) -> AgentAnswer:
        plan = self.plan(question, tables)
        result = execute_plan(plan, tables)
        actual_name = self.name if os.getenv("ANTHROPIC_API_KEY") else self.name + " — modo offline"
        return AgentAnswer(format_answer(question, plan, result), result, plan, actual_name)


def format_answer(question: str, plan: QueryPlan, result: pd.DataFrame) -> str:
    if result.empty:
        return "Não encontrei registros para essa pergunta."
    if not plan.group_by and len(result) == 1 and plan.aggregations:
        alias = plan.aggregations[0].alias
        value = result.iloc[0][alias]
        if "media" in norm(question):
            return f"A média calculada é **{money(value)}**."
        if plan.aggregations[0].function == "sum":
            return f"O total calculado é **{money(value)}**."
        return f"O resultado calculado é **{number(value)}**."
    if plan.group_by and len(result) >= 1:
        key = plan.group_by[0] if plan.group_by[0] != "__MES__" else "MÊS"
        value_column_name = plan.aggregations[0].alias if plan.aggregations else None
        first = result.iloc[0]
        if value_column_name and value_column_name in first:
            value = first[value_column_name]
            is_quantity = "quant" in norm(plan.aggregations[0].alias)
            display = number(value) if is_quantity else (money(value) if plan.aggregations[0].function in {"sum", "avg", "min", "max"} else number(value))
            return f"Encontrei **{len(result)}** grupos. O primeiro é **{first[key]}**, com **{display}**."
        return f"Encontrei **{len(result)}** grupos para **{key}**."
    return f"Encontrei **{len(result)}** registros."
