from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .factors import calculate_factor


def run_monthly_rebalance_backtest(
    data: pd.DataFrame,
    factor_name: str,
    lookback: int = 60,
    top_pct: float = 0.2,
    initial_observation_ratio: float = 0.5,
):
    """执行月度调仓、因子选股、等权组合回测。"""
    if data.empty:
        raise ValueError("数据为空，无法回测。")
    if not 0 < top_pct <= 1:
        raise ValueError("top_pct 必须在 (0, 1] 范围内。")
    if not 0 <= initial_observation_ratio < 1:
        raise ValueError("initial_observation_ratio 必须在 [0, 1) 范围内。")

    data = data.sort_values(["stock_code", "date"]).copy()
    data["daily_return"] = data.groupby("stock_code")["close"].pct_change()
    trading_dates = pd.Series(sorted(data["date"].dropna().unique()))
    if len(trading_dates) < 3:
        raise ValueError("交易日数量过少，无法回测。")

    start_idx = int(len(trading_dates) * initial_observation_ratio)
    start_idx = min(max(start_idx, 1), len(trading_dates) - 2)
    backtest_dates = trading_dates.iloc[start_idx:].reset_index(drop=True)
    rebalance_dates = _get_monthly_rebalance_dates(backtest_dates)
    if not rebalance_dates:
        raise ValueError("正式回测期内没有可用调仓日。")

    portfolio_returns = []
    rebalance_records = []
    selected_details = []

    for idx, rebalance_date in enumerate(rebalance_dates):
        signal_pos = trading_dates[trading_dates < rebalance_date].index
        if len(signal_pos) == 0:
            continue
        signal_date = trading_dates.iloc[signal_pos[-1]]

        factor_df = calculate_factor(data, factor_name, signal_date, lookback)
        factor_df = factor_df.dropna(subset=["factor_value"])
        if factor_df.empty:
            continue

        factor_df = factor_df.sort_values("factor_value", ascending=False)
        num_selected = max(1, math.ceil(len(factor_df) * top_pct))
        selected = factor_df.head(num_selected).copy()
        selected_stocks = selected["stock_code"].tolist()
        weight = 1.0 / len(selected_stocks)

        next_rebalance_date = rebalance_dates[idx + 1] if idx + 1 < len(rebalance_dates) else None
        if next_rebalance_date is None:
            holding_dates = trading_dates[trading_dates >= rebalance_date]
        else:
            holding_dates = trading_dates[
                (trading_dates >= rebalance_date) & (trading_dates < next_rebalance_date)
            ]

        period_returns = _calculate_period_portfolio_returns(data, selected_stocks, holding_dates)
        portfolio_returns.extend(period_returns)

        rebalance_records.append(
            {
                "rebalance_date": rebalance_date,
                "signal_date": signal_date,
                "num_stocks": len(selected_stocks),
                "selected_stocks": ", ".join(selected_stocks),
                "factor_name": factor_name,
            }
        )
        for _, row in selected.iterrows():
            selected_details.append(
                {
                    "rebalance_date": rebalance_date,
                    "stock_code": row["stock_code"],
                    "factor_value": row["factor_value"],
                    "weight": weight,
                }
            )

    nav_df = pd.DataFrame(portfolio_returns)
    if nav_df.empty:
        raise ValueError("没有生成有效组合收益，可能是因子数据不足或回测区间过短。")

    nav_df = nav_df.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    nav_df["portfolio_return"] = nav_df["portfolio_return"].fillna(0)
    nav_df["nav"] = (1 + nav_df["portfolio_return"]).cumprod()
    nav_df.loc[0, "nav"] = 1 + nav_df.loc[0, "portfolio_return"]
    nav_df["drawdown"] = nav_df["nav"] / nav_df["nav"].cummax() - 1

    return nav_df, pd.DataFrame(rebalance_records), pd.DataFrame(selected_details)


def _get_monthly_rebalance_dates(dates: pd.Series) -> list[pd.Timestamp]:
    date_df = pd.DataFrame({"date": pd.to_datetime(dates)})
    date_df["year_month"] = date_df["date"].dt.to_period("M")
    return date_df.groupby("year_month")["date"].first().tolist()


def _calculate_period_portfolio_returns(
    data: pd.DataFrame,
    selected_stocks: list[str],
    holding_dates: pd.Series,
) -> list[dict]:
    if not selected_stocks or len(holding_dates) == 0:
        return []

    period_data = data[
        data["stock_code"].isin(selected_stocks) & data["date"].isin(holding_dates)
    ].copy()
    if period_data.empty:
        return []

    daily_returns = (
        period_data.groupby("date")["daily_return"]
        .mean()
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0)
        .reset_index(name="portfolio_return")
    )
    return daily_returns.to_dict("records")
