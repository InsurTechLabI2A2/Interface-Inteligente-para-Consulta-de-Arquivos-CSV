from __future__ import annotations

"""Safe, deterministic execution of the query plans produced by the agents."""

import re
from typing import Any

import pandas as pd

from .models import QueryPlan


def normalize_number_series(series: pd.Series) -> pd.Series:
    """Parse both Brazilian and plain numeric formats without changing the source frame."""
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce")
    raw = series.astype(str).str.strip().str.replace("R$", "", regex=False).str.replace(" ", "", regex=False)
    both = raw.str.contains(",", regex=False) & raw.str.contains(".", regex=False)
    brazilian = raw.where(~both, raw.str.replace(".", "", regex=False).str.replace(",", ".", regex=False))
    brazilian = brazilian.where(both | ~raw.str.contains(",", regex=False), raw.str.replace(",", ".", regex=False))
    return pd.to_numeric(brazilian, errors="coerce")


def month_series(series: pd.Series) -> pd.Series:
    raw = series.astype(str).str.strip()
    parsed = pd.to_datetime(raw, errors="coerce", dayfirst=True, format="mixed")
    return parsed.dt.to_period("M").astype(str).replace("NaT", pd.NA)


def _apply_filters(frame: pd.DataFrame, filters: list[Any]) -> pd.DataFrame:
    result = frame.copy()
    for condition in filters:
        if condition.column not in result.columns:
            continue
        series = result[condition.column]
        op = condition.operator
        if op == "contains":
            mask = series.astype(str).str.contains(condition.value, case=False, na=False)
        else:
            left = normalize_number_series(series)
            right = pd.to_numeric(condition.value, errors="coerce")
            if pd.isna(right):
                left = series.astype(str).str.casefold()
                right = condition.value.casefold()
            if op == "=":
                mask = left == right
            elif op == ">":
                mask = left > right
            elif op == ">=":
                mask = left >= right
            elif op == "<":
                mask = left < right
            else:
                mask = left <= right
        result = result.loc[mask]
    return result


def _aggregation(frame: pd.DataFrame, function: str, column: str) -> float | int:
    if function in {"sum", "avg", "min", "max"}:
        values = normalize_number_series(frame[column])
        if function == "sum":
            return float(values.sum())
        if function == "avg":
            return float(values.mean())
        if function == "min":
            return float(values.min())
        return float(values.max())
    if column == "*":
        return int(len(frame)) if function == "count" else int(frame.nunique().sum())
    if function == "count_distinct":
        return int(frame[column].nunique(dropna=True))
    return int(frame[column].count())


def execute_plan(plan: QueryPlan, tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    if plan.table not in tables:
        raise ValueError(f"A tabela '{plan.table}' não está carregada.")
    source = tables[plan.table]
    frame = _apply_filters(source, plan.filters)

    working = frame.copy()
    actual_group: list[str] = []
    for group in plan.group_by:
        if group == "__MES__":
            date_column = next(
                (column for column in working.columns if "data" in str(column).casefold() or "emissao" in str(column).casefold()),
                None,
            )
            if date_column is None:
                continue
            working["MÊS"] = month_series(working[date_column])
            actual_group.append("MÊS")
        elif group in working.columns:
            actual_group.append(group)

    if plan.aggregations:
        if actual_group:
            rows: list[dict[str, Any]] = []
            for keys, group_frame in working.groupby(actual_group, dropna=False, sort=False):
                key_tuple = keys if isinstance(keys, tuple) else (keys,)
                row = dict(zip(actual_group, key_tuple))
                for aggregation in plan.aggregations:
                    row[aggregation.alias] = _aggregation(group_frame, aggregation.function, aggregation.column)
                rows.append(row)
            result = pd.DataFrame(rows)
        else:
            result = pd.DataFrame(
                [{aggregation.alias: _aggregation(working, aggregation.function, aggregation.column) for aggregation in plan.aggregations}]
            )
    else:
        selected = [column for column in plan.select if column in working.columns]
        result = working[selected].copy() if selected else working.copy()

    if plan.order_by and plan.order_by.column in result.columns:
        sort_column = plan.order_by.column
        numeric_sort = normalize_number_series(result[sort_column])
        if numeric_sort.notna().any():
            result = result.assign(__sort_key=numeric_sort).sort_values(
                "__sort_key", ascending=not plan.order_by.descending, kind="stable"
            ).drop(columns=["__sort_key"])
        else:
            result = result.sort_values(sort_column, ascending=not plan.order_by.descending, kind="stable")
    if plan.limit is not None:
        result = result.head(max(1, plan.limit))
    return result.reset_index(drop=True)


def money(value: Any) -> str:
    if pd.isna(value):
        return "n/d"
    return f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def number(value: Any) -> str:
    if pd.isna(value):
        return "n/d"
    numeric = float(value)
    if numeric.is_integer():
        return f"{int(numeric):,}".replace(",", ".")
    return f"{numeric:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
