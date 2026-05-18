from __future__ import annotations

import pandas as pd


TRADING_DAYS_PER_YEAR = 252


def ensure_datetime(series: pd.Series) -> pd.Series:
    """将日期列转换为 pandas datetime。"""
    return pd.to_datetime(series, errors="coerce")


def format_pct(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{value:.2%}"


def format_float(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{value:.4f}"
