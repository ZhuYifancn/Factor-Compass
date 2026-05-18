from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from src.backtest import run_monthly_rebalance_backtest
from src.data_loader import load_and_clean_data, summarize_data
from src.factors import FACTOR_DEFINITIONS
from src.metrics import calculate_metrics
from src.utils import format_float, format_pct


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_PATH = BASE_DIR / "data" / "default_prices.csv"


st.set_page_config(page_title="因子投资月度调仓回测系统", layout="wide")
st.title("因子投资月度调仓回测系统")


@st.cache_data(show_spinner=False)
def load_data_cached(uploaded_file):
    return load_and_clean_data(uploaded_file, DEFAULT_DATA_PATH)


with st.sidebar:
    st.header("数据与参数")
    uploaded_file = st.file_uploader("上传 CSV", type=["csv"])

try:
    data = load_data_cached(uploaded_file)
    summary = summarize_data(data)
except Exception as exc:
    st.error(f"数据读取失败：{exc}")
    st.stop()

available_factors = summary["available_factors"]
if not available_factors:
    st.error("当前数据没有可用因子，请至少提供 stock_code、date、close 字段。")
    st.stop()

with st.sidebar:
    factor_name = st.selectbox(
        "选择因子",
        available_factors,
        format_func=lambda x: f"{FACTOR_DEFINITIONS[x]['name']} ({x})",
    )
    lookback = st.number_input("lookback 回看窗口", min_value=5, max_value=252, value=60, step=5)
    top_pct = st.slider("top_pct 选股比例", min_value=0.05, max_value=1.0, value=0.2, step=0.05)
    initial_observation_ratio = st.slider(
        "initial_observation_ratio 初始观察期比例",
        min_value=0.1,
        max_value=0.8,
        value=0.5,
        step=0.05,
    )
    run_button = st.button("运行回测", type="primary")

st.subheader("数据概览")
col1, col2, col3, col4 = st.columns(4)
col1.metric("股票数量", summary["num_stocks"])
col2.metric("交易日数量", summary["num_dates"])
col3.metric("开始日期", summary["start_date"].strftime("%Y-%m-%d"))
col4.metric("结束日期", summary["end_date"].strftime("%Y-%m-%d"))

st.write("当前数据字段：", ", ".join(summary["columns"]))
st.write(
    "当前可用因子：",
    ", ".join([f"{FACTOR_DEFINITIONS[name]['name']} ({name})" for name in available_factors]),
)

factor_info = FACTOR_DEFINITIONS[factor_name]
st.subheader("因子说明")
info_col1, info_col2, info_col3 = st.columns(3)
info_col1.write(f"**因子含义**：{factor_info['description']}")
info_col2.write(f"**依赖字段**：{', '.join(factor_info['fields'])}")
info_col3.write("**因子方向**：factor_value 越大越好")

if run_button:
    try:
        with st.spinner("正在运行回测..."):
            nav_df, rebalance_records, selected_details = run_monthly_rebalance_backtest(
                data=data,
                factor_name=factor_name,
                lookback=int(lookback),
                top_pct=float(top_pct),
                initial_observation_ratio=float(initial_observation_ratio),
            )
            metrics = calculate_metrics(nav_df)
    except Exception as exc:
        st.error(f"回测失败：{exc}")
        st.stop()

    st.subheader("回测结果")
    avg_num_stocks = (
        rebalance_records["num_stocks"].mean() if not rebalance_records.empty else pd.NA
    )
    metric_cols = st.columns(6)
    metric_cols[0].metric("累计收益率", format_pct(metrics["cumulative_return"]))
    metric_cols[1].metric("年化收益率", format_pct(metrics["annual_return"]))
    metric_cols[2].metric("年化波动率", format_pct(metrics["annual_volatility"]))
    metric_cols[3].metric("夏普比率", format_float(metrics["sharpe_ratio"]))
    metric_cols[4].metric("最大回撤", format_pct(metrics["max_drawdown"]))
    metric_cols[5].metric("调仓次数", len(rebalance_records))
    st.metric("平均持股数量", format_float(avg_num_stocks))

    st.subheader("图表")
    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        st.plotly_chart(
            px.line(nav_df, x="date", y="nav", title="组合净值曲线"),
            use_container_width=True,
        )
    with chart_col2:
        st.plotly_chart(
            px.line(nav_df, x="date", y="drawdown", title="回撤曲线"),
            use_container_width=True,
        )
    st.plotly_chart(
        px.line(nav_df, x="date", y="portfolio_return", title="每日收益率曲线"),
        use_container_width=True,
    )

    st.subheader("调仓记录")
    if not rebalance_records.empty:
        display_records = rebalance_records.copy()
        display_records["rebalance_date"] = pd.to_datetime(display_records["rebalance_date"]).dt.strftime(
            "%Y-%m-%d"
        )
        display_records["signal_date"] = pd.to_datetime(display_records["signal_date"]).dt.strftime(
            "%Y-%m-%d"
        )
        st.dataframe(display_records, use_container_width=True)
    else:
        st.info("没有调仓记录。")

    st.subheader("每次调仓选中股票及因子值")
    if not selected_details.empty:
        display_details = selected_details.copy()
        display_details["rebalance_date"] = pd.to_datetime(
            display_details["rebalance_date"]
        ).dt.strftime("%Y-%m-%d")
        st.dataframe(display_details, use_container_width=True)

        last_rebalance_date = selected_details["rebalance_date"].max()
        last_positions = selected_details[
            selected_details["rebalance_date"] == last_rebalance_date
        ].copy()
        last_positions = last_positions.sort_values("factor_value", ascending=False)
        st.subheader("最后一次调仓持仓列表")
        st.dataframe(last_positions, use_container_width=True)
    else:
        st.info("没有选股明细。")
else:
    st.info("设置参数后点击“运行回测”。默认数据会在首次使用时自动生成。")
