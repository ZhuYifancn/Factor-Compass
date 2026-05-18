from __future__ import annotations

import numpy as np
import pandas as pd


FACTOR_DEFINITIONS = {
    "momentum": {
        "name": "动量因子",
        "fields": ["close"],
        "description": "过去一段时间价格涨幅越高，因子值越大。",
    },
    "reversal": {
        "name": "反转因子",
        "fields": ["close"],
        "description": "过去一段时间跌幅越大，反转因子值越大。",
    },
    "low_volatility": {
        "name": "低波动因子",
        "fields": ["close"],
        "description": "过去收益率波动越低，因子值越大。",
    },
    "ma_bias": {
        "name": "均线偏离因子",
        "fields": ["close"],
        "description": "当前价格相对过去均线越强，因子值越大。",
    },
    "intraday_strength": {
        "name": "日内强弱因子",
        "fields": ["open", "close"],
        "description": "过去一段时间从开盘到收盘的平均表现越强，因子值越大。",
    },
    "range_volatility": {
        "name": "振幅波动因子",
        "fields": ["high", "low", "close"],
        "description": "过去日内振幅越低，因子值越大。",
    },
    "volume_momentum": {
        "name": "成交量动量因子",
        "fields": ["volume"],
        "description": "近期成交量相对长窗口放大越明显，因子值越大。",
    },
    "liquidity": {
        "name": "流动性因子",
        "fields": ["amount"],
        "description": "过去平均成交额越高，因子值越大。",
    },
    "illiquidity": {
        "name": "非流动性因子",
        "fields": ["amount", "close"],
        "description": "单位成交额带来的价格波动越低，因子值越大。",
    },
}


def get_available_factors(data: pd.DataFrame) -> list[str]:
    columns = set(data.columns)
    available = []
    for factor_name, definition in FACTOR_DEFINITIONS.items():
        if set(definition["fields"]).issubset(columns):
            available.append(factor_name)
    return available


def _check_factor_inputs(data: pd.DataFrame, factor_name: str) -> None:
    if factor_name not in FACTOR_DEFINITIONS:
        raise ValueError(f"未知因子: {factor_name}")
    missing = [col for col in FACTOR_DEFINITIONS[factor_name]["fields"] if col not in data.columns]
    if missing:
        raise ValueError(f"因子 {factor_name} 缺少依赖字段: {', '.join(missing)}")


def _last_valid_value(series: pd.Series):
    series = series.dropna()
    if series.empty:
        return np.nan
    return series.iloc[-1]


def calculate_factor(
    data: pd.DataFrame,
    factor_name: str,
    as_of_date,
    lookback: int,
) -> pd.DataFrame:
    """按股票计算指定日期可见历史内的因子值。"""
    _check_factor_inputs(data, factor_name)
    if lookback <= 0:
        raise ValueError("lookback 必须大于 0。")

    as_of_date = pd.to_datetime(as_of_date)
    history = data[data["date"] <= as_of_date].copy()
    if history.empty:
        return pd.DataFrame(columns=["stock_code", "factor_value"])

    history = history.sort_values(["stock_code", "date"])
    results = []

    for stock_code, group in history.groupby("stock_code", sort=False):
        group = group.sort_values("date")
        if len(group) < lookback:
            factor_value = np.nan
        else:
            factor_value = _calculate_single_stock_factor(group, factor_name, lookback)
        results.append({"stock_code": stock_code, "factor_value": factor_value})

    return pd.DataFrame(results)


def _calculate_single_stock_factor(group: pd.DataFrame, factor_name: str, lookback: int) -> float:
    close = group["close"] if "close" in group.columns else None

    if factor_name == "momentum":
        if len(group) <= lookback or pd.isna(close.iloc[-lookback - 1]) or close.iloc[-lookback - 1] == 0:
            return np.nan
        return close.iloc[-1] / close.iloc[-lookback - 1] - 1

    if factor_name == "reversal":
        if len(group) <= lookback or pd.isna(close.iloc[-lookback - 1]) or close.iloc[-lookback - 1] == 0:
            return np.nan
        return -(close.iloc[-1] / close.iloc[-lookback - 1] - 1)

    if factor_name == "low_volatility":
        returns = close.pct_change().tail(lookback)
        return -_last_valid_value(pd.Series([returns.std(ddof=0)]))

    if factor_name == "ma_bias":
        window = close.tail(lookback)
        mean_close = window.mean()
        if pd.isna(mean_close) or mean_close == 0:
            return np.nan
        return close.iloc[-1] / mean_close - 1

    if factor_name == "intraday_strength":
        intraday = group["close"] / group["open"] - 1
        intraday = intraday.replace([np.inf, -np.inf], np.nan).tail(lookback)
        return intraday.mean()

    if factor_name == "range_volatility":
        price_range = (group["high"] - group["low"]) / group["close"]
        price_range = price_range.replace([np.inf, -np.inf], np.nan).tail(lookback)
        return -price_range.mean()

    if factor_name == "volume_momentum":
        volume = group["volume"].tail(lookback)
        recent_window = max(5, lookback // 2)
        long_mean = volume.mean()
        recent_mean = group["volume"].tail(recent_window).mean()
        if pd.isna(long_mean) or long_mean == 0:
            return np.nan
        return recent_mean / long_mean - 1

    if factor_name == "liquidity":
        amount = group["amount"].tail(lookback)
        return amount.mean()

    if factor_name == "illiquidity":
        returns = group["close"].pct_change().abs()
        amihud = returns / group["amount"]
        amihud = amihud.replace([np.inf, -np.inf], np.nan).tail(lookback)
        value = amihud.mean()
        if pd.isna(value):
            return np.nan
        return -value

    raise ValueError(f"未知因子: {factor_name}")
