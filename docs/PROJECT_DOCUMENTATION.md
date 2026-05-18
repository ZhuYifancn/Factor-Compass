# 因子投资月度调仓回测系统项目文档

## 1. 项目目标

本项目是一个教学和研究用途的因子投资回测 demo。系统支持用户上传股票行情 CSV，也支持使用自动生成的默认模拟行情数据。页面通过 Streamlit 展示数据概览、因子选择、回测参数、绩效指标、净值曲线、回撤曲线、每日收益率曲线、调仓记录和持仓明细。

系统核心目标：

- 兼容旧版 CSV：只要包含 `stock_code,date,close` 即可运行。
- 扩展 OHLCV 字段：若存在 `open,high,low,volume,amount`，自动启用更多因子。
- 保持模块清晰：数据加载、因子计算、回测、指标和页面展示分离。
- 避免未来函数：所有调仓信号都只使用调仓日前一个交易日及以前的数据。
- 便于后续扩展：可继续增加因子、交易规则、风险控制或网站化后端。

## 2. 项目结构

```text
factor_backtest_demo/
  app.py
  requirements.txt
  README.md
  data/
    default_prices.csv
  docs/
    PROJECT_DOCUMENTATION.md
  src/
    __init__.py
    data_loader.py
    factors.py
    backtest.py
    metrics.py
    utils.py
```

各模块职责：

| 文件 | 职责 |
| --- | --- |
| `app.py` | Streamlit 页面入口，负责交互、参数设置、结果展示 |
| `src/data_loader.py` | 读取 CSV、清洗字段、生成默认数据、汇总数据状态 |
| `src/factors.py` | 因子定义、可用因子判断、统一因子计算 |
| `src/backtest.py` | 月度调仓回测、选股、持仓收益和净值计算 |
| `src/metrics.py` | 绩效指标计算 |
| `src/utils.py` | 通用常量和格式化函数 |
| `README.md` | 快速运行说明和字段/因子说明 |

## 3. 数据逻辑

### 3.1 字段要求

必需字段：

- `stock_code`：股票代码
- `date`：交易日期
- `close`：收盘价

可选字段：

- `open`：开盘价
- `high`：最高价
- `low`：最低价
- `volume`：成交量
- `amount`：成交额

### 3.2 清洗流程

`clean_price_data()` 的处理流程：

1. 去除字段名前后空格。
2. 检查必需字段 `stock_code,date,close`，缺少则抛出错误。
3. 将 `date` 转为 datetime。
4. 将 `open,high,low,close,volume,amount` 中存在的列转为数值。
5. 删除 `stock_code,date,close` 缺失的数据。
6. 删除 `close <= 0` 的数据。
7. 如果 `amount` 不存在但 `volume` 存在，生成 `amount = close * volume`。
8. 按 `stock_code,date` 排序。

可选字段缺失不会导致系统整体失败，只会影响相关因子的可用性。

### 3.3 默认数据生成

如果 `data/default_prices.csv` 不存在，`generate_default_data()` 会自动生成模拟数据：

- 股票数量：50 只。
- 交易日数量：500 个工作日。
- 股票代码：`STOCK_001` 到 `STOCK_050`。
- `close`：随机游走生成，并保证价格为正。
- `open`：基于前一日收盘价加入小幅扰动。
- `high`：不低于 `max(open, close)`。
- `low`：不高于 `min(open, close)`。
- `volume`：随机正整数。
- `amount = close * volume`。
- 随机种子固定为 42，保证结果可复现。

## 4. 因子逻辑

因子统一通过 `calculate_factor(data, factor_name, as_of_date, lookback)` 计算，返回：

```text
stock_code
factor_value
```

关键约束：

- 只使用 `date <= as_of_date` 的数据。
- 对每只股票单独计算。
- 历史数据不足时返回空因子值。
- 缺少依赖字段时抛出清晰错误。
- 所有因子方向统一为 `factor_value` 越大越好。

### 4.1 因子可用性判断

`get_available_factors(data)` 根据字段自动判断：

| 因子 | 依赖字段 |
| --- | --- |
| `momentum` | `close` |
| `reversal` | `close` |
| `low_volatility` | `close` |
| `ma_bias` | `close` |
| `intraday_strength` | `open, close` |
| `range_volatility` | `high, low, close` |
| `volume_momentum` | `volume` |
| `liquidity` | `amount` |
| `illiquidity` | `amount, close` |

若用户只上传 `stock_code,date,close`，页面只展示前 4 个因子。

### 4.2 具体因子实现

`momentum`：

```text
close_t / close_{t-lookback} - 1
```

`reversal`：

```text
-(close_t / close_{t-lookback} - 1)
```

`low_volatility`：

```text
-std(daily_return over past lookback days)
```

`ma_bias`：

```text
close_t / mean(close over past lookback days) - 1
```

`intraday_strength`：

```text
mean(close / open - 1 over past lookback days)
```

`range_volatility`：

```text
-mean((high - low) / close over past lookback days)
```

`volume_momentum`：

```text
mean(volume over recent_window) / mean(volume over lookback) - 1
recent_window = max(5, lookback // 2)
```

`liquidity`：

```text
mean(amount over past lookback days)
```

`illiquidity`：

```text
daily_return = close / close.shift(1) - 1
amihud = mean(abs(daily_return) / amount over past lookback days)
illiquidity = -amihud
```

## 5. 回测逻辑

核心函数：

```python
run_monthly_rebalance_backtest(
    data,
    factor_name,
    lookback=60,
    top_pct=0.2,
    initial_observation_ratio=0.5,
)
```

### 5.1 交易日和调仓日

1. 取全市场所有交易日并排序。
2. 使用 `initial_observation_ratio` 切分初始观察期和正式回测期。
3. 正式回测期从后半段日期开始。
4. 正式回测期内，每个月第一个交易日作为调仓日。

### 5.2 调仓流程

每个调仓日执行：

1. 找到调仓日前一个可用交易日作为 `signal_date`。
2. 用 `date <= signal_date` 的历史数据计算因子。
3. 删除 `factor_value` 为空的股票。
4. 按 `factor_value` 从大到小排序。
5. 选择前 `top_pct` 股票，最少选择 1 只。
6. 选中股票等权持有。
7. 持有到下一个调仓日前一个交易日。
8. 持有期每日组合收益率为选中股票每日收益率的等权平均。

### 5.3 回测输出

`nav_df`：

| 字段 | 含义 |
| --- | --- |
| `date` | 交易日期 |
| `portfolio_return` | 组合每日收益率 |
| `nav` | 组合净值 |
| `drawdown` | 回撤 |

`rebalance_records`：

| 字段 | 含义 |
| --- | --- |
| `rebalance_date` | 调仓日 |
| `signal_date` | 信号计算日 |
| `num_stocks` | 持股数量 |
| `selected_stocks` | 选中股票 |
| `factor_name` | 使用因子 |

`selected_details`：

| 字段 | 含义 |
| --- | --- |
| `rebalance_date` | 调仓日 |
| `stock_code` | 股票代码 |
| `factor_value` | 因子值 |
| `weight` | 等权权重 |

## 6. 指标逻辑

`calculate_metrics(nav_df)` 计算：

- 累计收益率
- 年化收益率
- 年化波动率
- 夏普比率
- 最大回撤

年化交易日假设为 252 天。若收益为空、波动率为 0 或数据不足，相关指标返回空值，避免页面崩溃。

## 7. 页面逻辑

`app.py` 页面分为以下区域：

1. 数据上传区域：支持上传 CSV，不上传时使用默认数据。
2. 数据概览：展示字段、股票数量、交易日数量、日期范围和可用因子。
3. 参数设置：选择因子、`lookback`、`top_pct`、`initial_observation_ratio`。
4. 因子说明：展示因子含义、依赖字段、方向。
5. 回测结果：展示绩效指标、调仓次数、平均持股数量。
6. 图表区域：净值曲线、回撤曲线、每日收益率曲线。
7. 表格区域：调仓记录、调仓选股详情、最后一次持仓。

页面因子选择框只展示当前数据支持的因子，因此可选字段缺失时不会出现不可运行的因子。

## 8. 异常处理

系统已处理以下常见情况：

- 缺少必需字段：明确提示缺少字段。
- 可选字段缺失：隐藏对应因子。
- `amount` 缺失但有 `volume`：自动生成成交额。
- 日期或数值列格式异常：转换失败后变为空值并在必要步骤剔除。
- 历史数据不足：该股票因子值为空，选股前删除。
- 因子结果为空：回测阶段给出错误提示。
- 波动率为 0：夏普比率返回空值。

## 9. 后续扩展方向

可以在当前结构上继续扩展：

- 增加更多技术类、基本面类或组合因子。
- 增加行业中性、市值中性、停牌过滤等约束。
- 增加手续费、滑点、涨跌停不可交易等交易细节。
- 支持多因子加权打分。
- 将 Streamlit demo 改造为 Flask/FastAPI 后端加前端页面。
- 增加回测结果导出和参数保存功能。

## 10. 运行与验证

安装依赖：

```bash
pip install -r requirements.txt
```

启动页面：

```bash
streamlit run app.py
```

已验证：

- 默认 OHLCV 数据可自动生成。
- 默认数据下 9 个因子均可用。
- 只含 `stock_code,date,close` 的旧版数据可以正常运行。
- 旧版数据只展示 4 个 close 因子。
- 月度调仓回测可以生成净值、调仓记录和持仓明细。
