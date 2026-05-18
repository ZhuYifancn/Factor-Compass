from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .factors import get_available_factors
from .utils import ensure_datetime


REQUIRED_COLUMNS = ["stock_code", "date", "close"]
OPTIONAL_COLUMNS = ["open", "high", "low", "volume", "amount"]
NUMERIC_COLUMNS = ["open", "high", "low", "close", "volume", "amount"]


def generate_default_data(
    output_path: str | Path,
    num_stocks: int = 50,
    num_days: int = 500,
    seed: int = 42,
) -> pd.DataFrame:
    """生成可复现的 OHLCV 模拟数据，并保存到 CSV。"""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=num_days)
    records = []

    for stock_idx in range(1, num_stocks + 1):
        stock_code = f"STOCK_{stock_idx:03d}"
        start_price = rng.uniform(15, 120)
        daily_returns = rng.normal(loc=0.0003, scale=0.02, size=num_days)
        close = start_price * np.cumprod(1 + daily_returns)
        close = np.maximum(close, 1.0)

        prev_close = np.roll(close, 1)
        prev_close[0] = close[0] / max(1 + daily_returns[0], 0.5)
        open_price = prev_close * (1 + rng.normal(0, 0.006, size=num_days))
        open_price = np.maximum(open_price, 0.5)

        high_base = np.maximum(open_price, close)
        low_base = np.minimum(open_price, close)
        high = high_base * (1 + rng.uniform(0, 0.025, size=num_days))
        low = low_base * (1 - rng.uniform(0, 0.025, size=num_days))
        low = np.maximum(low, 0.01)

        volume = rng.integers(100_000, 8_000_000, size=num_days)
        amount = close * volume

        for i, date in enumerate(dates):
            records.append(
                {
                    "stock_code": stock_code,
                    "date": date,
                    "open": open_price[i],
                    "high": high[i],
                    "low": low[i],
                    "close": close[i],
                    "volume": volume[i],
                    "amount": amount[i],
                }
            )

    data = pd.DataFrame(records)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data.to_csv(output_path, index=False)
    return data


def load_default_data(default_path: str | Path) -> pd.DataFrame:
    path = Path(default_path)
    if not path.exists():
        return generate_default_data(path)
    return pd.read_csv(path)


def clean_price_data(data: pd.DataFrame) -> pd.DataFrame:
    """校验必需字段并清洗行情数据；可选字段缺失不报错。"""
    data = data.copy()
    data.columns = [str(col).strip() for col in data.columns]

    missing_required = [col for col in REQUIRED_COLUMNS if col not in data.columns]
    if missing_required:
        raise ValueError(f"CSV 缺少必需字段: {', '.join(missing_required)}")

    data["stock_code"] = data["stock_code"].astype(str).str.strip()
    data["date"] = ensure_datetime(data["date"])

    for col in NUMERIC_COLUMNS:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors="coerce")

    # 只删除必需字段缺失的数据，避免可选字段缺失导致整体不可用。
    data = data.dropna(subset=REQUIRED_COLUMNS)
    data = data[data["close"] > 0]

    if "amount" not in data.columns and "volume" in data.columns:
        data["amount"] = data["close"] * data["volume"]

    data = data.sort_values(["stock_code", "date"]).reset_index(drop=True)
    return data


def load_and_clean_data(source, default_path: str | Path | None = None) -> pd.DataFrame:
    if source is None:
        if default_path is None:
            raise ValueError("未提供上传文件或默认数据路径。")
        raw = load_default_data(default_path)
    else:
        raw = pd.read_csv(source)
    return clean_price_data(raw)


def summarize_data(data: pd.DataFrame) -> dict:
    return {
        "columns": list(data.columns),
        "num_stocks": int(data["stock_code"].nunique()),
        "num_dates": int(data["date"].nunique()),
        "start_date": data["date"].min(),
        "end_date": data["date"].max(),
        "available_factors": get_available_factors(data),
    }
