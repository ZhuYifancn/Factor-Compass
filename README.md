# Factor Compass | 因子罗盘

Factor Compass 是一个轻量、可运行、便于扩展的因子投资月度调仓回测系统。项目使用 Python、Streamlit、Pandas、NumPy 和 Plotly 构建，适合用于量化投资教学、因子研究演示、策略原型验证，以及后续扩展为 Web 回测平台。

系统支持上传股票行情 CSV，并根据数据字段自动判断可用因子。只提供 `stock_code,date,close` 也能运行；如果数据包含 `open,high,low,volume,amount`，系统会自动启用更多 OHLCV 相关因子。

> 本项目仅用于教学、研究和技术演示，不构成任何投资建议。

## Highlights

- 自动生成默认模拟行情数据，克隆后即可体验。
- 兼容最简 CSV 格式：`stock_code,date,close`。
- 支持 OHLCV 扩展字段，并自动启用更多因子。
- 内置 9 类常见因子：动量、反转、低波动、均线偏离、日内强弱、振幅波动、成交量动量、流动性、非流动性。
- 实现月度调仓、因子排名选股、等权持仓和净值回测。
- 使用 Plotly 展示净值曲线、回撤曲线和每日收益率曲线。
- 展示绩效指标、调仓记录、选股明细和最后一期持仓。
- 模块化结构清晰，便于继续扩展因子、交易规则和前端页面。

## Demo Workflow

1. 上传 CSV 或使用默认模拟数据。
2. 系统清洗数据并识别当前可用因子。
3. 选择因子和回测参数。
4. 每月第一个交易日调仓，使用调仓日前一个交易日计算信号。
5. 按因子值从高到低选股，等权持有到下一次调仓。
6. 输出净值、回撤、绩效指标和持仓明细。

## Quick Start

```bash
git clone https://github.com/ZhuYifancn/Factor-Compass.git
cd Factor-Compass
pip install -r requirements.txt
streamlit run app.py
```

启动后，在浏览器中打开 Streamlit 输出的地址，通常是：

```text
http://localhost:8501
```

如果只希望绑定本机地址，可以使用：

```bash
streamlit run app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true
```

如果 `data/default_prices.csv` 不存在，系统会自动生成不少于 50 只股票、500 个交易日的模拟 OHLCV 数据。

## How To Use

1. 启动 Streamlit 页面。
2. 不上传 CSV 时，系统自动使用默认模拟数据。
3. 使用自己的数据时，在左侧侧边栏点击“上传 CSV”。
4. 页面会展示当前字段、股票数量、交易日数量、日期范围和可用因子。
5. 选择因子，并设置 `lookback`、`top_pct` 和 `initial_observation_ratio`。
6. 点击“运行回测”，查看指标、图表、调仓记录和持仓明细。

常用参数：

| 参数 | 含义 | 默认值 |
| --- | --- | --- |
| `lookback` | 因子计算回看窗口 | 60 |
| `top_pct` | 每次调仓选择因子排名靠前股票的比例 | 0.2 |
| `initial_observation_ratio` | 初始观察期比例，正式回测从后半段数据开始 | 0.5 |

## CSV Format

必需字段：

| 字段 | 含义 |
| --- | --- |
| `stock_code` | 股票代码 |
| `date` | 交易日期 |
| `close` | 收盘价 |

可选字段：

| 字段 | 含义 |
| --- | --- |
| `open` | 开盘价 |
| `high` | 最高价 |
| `low` | 最低价 |
| `volume` | 成交量 |
| `amount` | 成交额 |

字段处理规则：

- `stock_code,date,close` 是必需字段。
- `open,high,low,volume,amount` 是可选字段。
- 如果缺少 `amount` 但存在 `close` 和 `volume`，系统会自动生成 `amount = close * volume`。
- 可选字段缺失不会导致系统崩溃，只会隐藏依赖这些字段的因子。

## Factors

所有因子统一为 `factor_value` 越大越好。

| 因子 | 依赖字段 | 说明 |
| --- | --- | --- |
| `momentum` | `close` | 过去一段时间价格涨幅越高越好 |
| `reversal` | `close` | 过去一段时间跌幅越大，反转因子越高 |
| `low_volatility` | `close` | 过去收益率波动越低越好 |
| `ma_bias` | `close` | 当前价格相对过去均线越强越好 |
| `intraday_strength` | `open, close` | 开盘到收盘的平均表现越强越好 |
| `range_volatility` | `high, low, close` | 日内振幅越低越稳定 |
| `volume_momentum` | `volume` | 近期成交量相对长窗口放大越明显越好 |
| `liquidity` | `amount` | 平均成交额越高越好 |
| `illiquidity` | `amount, close` | 单位成交额带来的价格波动越低越好 |

## Backtest Logic

系统使用月度调仓：

1. 获取全部交易日并排序。
2. 使用 `initial_observation_ratio` 划分初始观察期和正式回测期。
3. 在正式回测期内，每个月第一个交易日调仓。
4. 调仓信号使用调仓日前一个可用交易日的数据计算，避免未来函数。
5. 每次按因子值降序选择前 `top_pct` 股票，至少选择 1 只。
6. 选中股票等权配置，持有到下一个调仓日前。
7. 输出净值、回撤、每日收益率、调仓记录和持仓明细。

## Project Structure

```text
Factor-Compass/
  app.py
  requirements.txt
  README.md
  data/
    default_prices.csv
  docs/
    PROJECT_DOCUMENTATION.md
  src/
    data_loader.py
    factors.py
    backtest.py
    metrics.py
    utils.py
```

## Documentation

更完整的项目逻辑、模块职责、数据流、因子实现和回测细节见：

```text
docs/PROJECT_DOCUMENTATION.md
```

## Disclaimer

Factor Compass 仅用于教学、研究和技术演示。项目中的模拟数据、因子逻辑和回测结果不代表真实市场表现，不构成任何投资建议。
