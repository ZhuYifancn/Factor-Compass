from __future__ import annotations

import numpy as np
import pandas as pd

from .utils import TRADING_DAYS_PER_YEAR


def calculate_metrics(nav_df: pd.DataFrame) -> dict:
    if nav_df.empty or "portfolio_return" not in nav_df.columns:
        return _empty_metrics()

    returns = nav_df["portfolio_return"].dropna()
    if returns.empty:
        return _empty_metrics()

    nav = nav_df["nav"].dropna()
    if nav.empty:
        return _empty_metrics()

    cumulative_return = nav.iloc[-1] / nav.iloc[0] - 1 if nav.iloc[0] != 0 else np.nan
    num_days = max(len(returns), 1)
    annual_return = (1 + cumulative_return) ** (TRADING_DAYS_PER_YEAR / num_days) - 1
    annual_volatility = returns.std(ddof=0) * np.sqrt(TRADING_DAYS_PER_YEAR)
    sharpe_ratio = annual_return / annual_volatility if annual_volatility and annual_volatility > 0 else np.nan
    max_drawdown = nav_df["drawdown"].min() if "drawdown" in nav_df.columns else np.nan

    return {
        "cumulative_return": cumulative_return,
        "annual_return": annual_return,
        "annual_volatility": annual_volatility,
        "sharpe_ratio": sharpe_ratio,
        "max_drawdown": max_drawdown,
    }


def _empty_metrics() -> dict:
    return {
        "cumulative_return": np.nan,
        "annual_return": np.nan,
        "annual_volatility": np.nan,
        "sharpe_ratio": np.nan,
        "max_drawdown": np.nan,
    }
