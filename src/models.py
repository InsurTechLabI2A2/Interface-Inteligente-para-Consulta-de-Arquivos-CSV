from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class FilterCondition(BaseModel):
    column: str
    operator: Literal["=", "contains", ">", ">=", "<", "<="] = "="
    value: str


class Aggregation(BaseModel):
    function: Literal["sum", "avg", "count", "count_distinct", "min", "max"]
    column: str = "*"
    alias: str


class OrderBy(BaseModel):
    column: str
    descending: bool = True


class QueryPlan(BaseModel):
    table: str
    select: list[str] = Field(default_factory=list)
    filters: list[FilterCondition] = Field(default_factory=list)
    group_by: list[str] = Field(default_factory=list)
    aggregations: list[Aggregation] = Field(default_factory=list)
    order_by: OrderBy | None = None
    limit: int | None = 10
    output_type: Literal["text", "table", "chart"] = "table"
    chart_type: Literal["bar", "line", "pie"] | None = None
    explanation: str = ""


class QueryResponse(BaseModel):
    question: str
    plan: QueryPlan
    data: object | None = None
    text: str = ""
    agent_name: str = "Agente local determinístico"

