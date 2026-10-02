"""Biểu đồ minh hoạ động bằng Plotly cho từng phần phân tích."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

BLUE = "#0A4D8C"
ACCENT = "#1E88E5"
LIGHTBLUE = "#7FB3E3"
GOLD = "#E9A23B"
RED = "#C0392B"
GREEN = "#1E8E5A"
GRAY = "#5B6B7C"

PALETTE = [BLUE, ACCENT, LIGHTBLUE, GOLD, GREEN, "#8E44AD", RED, "#16A085"]
FONT = "Be Vietnam Pro, Segoe UI, sans-serif"


def _base(title: str) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        title=dict(text=title, font=dict(size=15, color=BLUE, family=FONT)),
        template="plotly_white",
        font=dict(family=FONT, size=12, color="#22303C"),
        margin=dict(l=10, r=10, t=45, b=10),
        height=340,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_xaxes(gridcolor="#EAF2FB")
    fig.update_yaxes(gridcolor="#EAF2FB")
    return fig


def show(fig: go.Figure | None, key: str | None = None) -> None:
    """Hiển thị biểu đồ (bỏ qua nếu không có dữ liệu vẽ)."""
    if fig is None:
        return
    st.plotly_chart(fig, use_container_width=True, key=key)


# ---------------------------------------------------------------------------
# 1. Tổng quan & phân phối
# ---------------------------------------------------------------------------
def hist_normal(df: pd.DataFrame, col: str) -> go.Figure | None:
    """Biểu đồ histogram phủ lớp đường phân phối chuẩn để thấy bản chất dữ liệu."""
    s = pd.to_numeric(df[col], errors="coerce").dropna()
    if s.empty:
        return None
    fig = _base(f"Phân phối của <b>{col}</b> — so với đường phân phối chuẩn")
    counts, edges = np.histogram(s, bins=min(40, max(10, int(len(s) ** 0.5))))
    centers = (edges[:-1] + edges[1:]) / 2
    width = edges[1] - edges[0]
    fig.add_trace(
        go.Bar(
            x=centers,
            y=counts,
            width=width,
            name="Tần suất thực nghiệm",
            marker_color=LIGHTBLUE,
            opacity=0.85,
            hovertemplate="%{x:.2f}<br>Tần suất: %{y}<extra></extra>",
        )
    )
    mu, sigma = float(s.mean()), float(s.std(ddof=1)) if len(s) > 1 else 1.0
    if sigma > 0:
        xs = np.linspace(edges[0], edges[-1], 200)
        pdf = 1 / (sigma * np.sqrt(2 * np.pi)) * np.exp(-((xs - mu) ** 2) / (2 * sigma**2))
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=pdf * len(s) * width,
                name="Phân phối chuẩn lý thuyết",
                mode="lines",
                line=dict(color=RED, width=2.5, dash="dash"),
            )
        )
    fig.update_layout(barmode="overlay")
    return fig


def type_donut(n_num: int, n_cat: int) -> go.Figure:
    fig = _base("Cơ cấu biến trong bộ dữ liệu")
    fig.add_trace(
        go.Pie(
            labels=["Biến định lượng", "Biến phân loại"],
            values=[max(n_num, 0.001), max(n_cat, 0.001)],
            hole=0.55,
            marker=dict(colors=[BLUE, GOLD], line=dict(color="#fff", width=2)),
            textinfo="label+value",
        )
    )
    return fig


def boxplot_numeric(df: pd.DataFrame, cols: list[str]) -> go.Figure | None:
    cols = [c for c in cols if pd.to_numeric(df[c], errors="coerce").notna().any()]
    if not cols:
        return None
    fig = _base("Phân tán và giá trị ngoại lai (Boxplot)")
    for i, c in enumerate(cols[:8]):
        fig.add_trace(
            go.Box(
                y=pd.to_numeric(df[c], errors="coerce").dropna(),
                name=str(c),
                marker_color=PALETTE[i % len(PALETTE)],
                boxpoints="outliers",
            )
        )
    return fig


# ---------------------------------------------------------------------------
# 2. Làm sạch & chất lượng dữ liệu
# ---------------------------------------------------------------------------
def missing_bar(missing_by_col: pd.DataFrame) -> go.Figure | None:
    if missing_by_col is None or missing_by_col.empty:
        return None
    fig = _base("Số ô thiếu dữ liệu theo từng cột")
    fig.add_trace(
        go.Bar(
            x=missing_by_col.iloc[:, 0].tolist(),
            y=missing_by_col.iloc[:, 1].tolist(),
            marker_color=GOLD,
            text=missing_by_col.iloc[:, 1].tolist(),
            textposition="outside",
            hovertemplate="%{x}<br>Thiếu: %{y} ô<extra></extra>",
        )
    )
    fig.update_layout(xaxis_title="Cột", yaxis_title="Số ô trống")
    return fig


def missing_matrix(df: pd.DataFrame) -> go.Figure | None:
    """Nhiệt đồ vị trí ô trống trong bộ dữ liệu."""
    n = min(len(df), 300)
    if n == 0 or df.shape[1] == 0:
        return None
    sub = df.head(n)
    z = sub.isna().astype(int).to_numpy().T
    fig = _base("Bản đồ ô trống (mỗi hàng = 1 quan sát, mỗi cột = 1 biến)")
    fig.add_trace(
        go.Heatmap(
            z=z,
            x=[str(c) for c in sub.columns],
            y=[f"#{i + 1}" for i in range(n)],
            colorscale=[[0, "#EAF2FB"], [1, RED]],
            showscale=False,
            hovertemplate="%{x}<br>Dòng %{y}<br>Ô trống: %{z}<extra></extra>",
        )
    )
    fig.update_layout(height=320)
    return fig


# ---------------------------------------------------------------------------
# 3. Thống kê mô tả & tương quan
# ---------------------------------------------------------------------------
def corr_heatmap(corr_mat: pd.DataFrame) -> go.Figure | None:
    if corr_mat is None or corr_mat.empty:
        return None
    fig = _base("Ma trận hệ số tương quan Pearson")
    fig.add_trace(
        go.Heatmap(
            z=corr_mat.to_numpy(),
            x=[str(c) for c in corr_mat.columns],
            y=[str(c) for c in corr_mat.index],
            colorscale=[[0, RED], [0.5, "#FFFFFF"], [1, BLUE]],
            zmid=0,
            zmin=-1,
            zmax=1,
            text=np.round(corr_mat.to_numpy(), 2),
            texttemplate="%{text}",
            hovertemplate="%{y} ↔ %{x}<br>r = %{z:.3f}<extra></extra>",
        )
    )
    fig.update_layout(height=400)
    return fig


def scatter_reg(
    df: pd.DataFrame, x: str, y: str, r: float | None = None, p: float | None = None
) -> go.Figure | None:
    xs = pd.to_numeric(df[x], errors="coerce")
    ys = pd.to_numeric(df[y], errors="coerce")
    m = xs.notna() & ys.notna()
    if m.sum() < 3:
        return None
    xs, ys = xs[m], ys[m]
    coef = np.polyfit(xs, ys, 1)
    slope, intercept = float(coef[0]), float(coef[1])

    fig = go.Figure()
    fig.add_trace(
        go.Scattergl(
            x=xs,
            y=ys,
            mode="markers",
            name="Quan sát",
            marker=dict(color=LIGHTBLUE, size=7, opacity=0.75, line=dict(width=0.5, color="#fff")),
            hovertemplate=f"{x}: %{{x:.2f}}<br>{y}: %{{y:.2f}}<extra></extra>",
        )
    )
    xline = np.linspace(xs.min(), xs.max(), 50)
    fig.add_trace(
        go.Scatter(
            x=xline,
            y=intercept + slope * xline,
            mode="lines",
            name=f"Đường hồi quy: y = {intercept:.2f} + {slope:.2f}x",
            line=dict(color=RED, width=3),
        )
    )
    sub = (
        f" · r = {r:.3f}"
        if r is not None
        else ""
    )
    psub = f" · p = {p:.4f}" if p is not None else ""
    fig.update_layout(
        title=dict(
            text=f"Tương quan <b>{y}</b> theo <b>{x}</b>{sub}{psub}",
            font=dict(size=15, color=BLUE, family=FONT),
        )
    )
    fig.update_xaxes(title_text=str(x))
    fig.update_yaxes(title_text=str(y))
    return fig


# ---------------------------------------------------------------------------
# 4. Độ tin cậy & EFA
# ---------------------------------------------------------------------------
def item_total_bar(df: pd.DataFrame, cols: list[str]) -> go.Figure | None:
    cols = [c for c in cols if c in df.columns]
    if len(cols) < 2:
        return None
    total = df[cols].sum(axis=1)
    corrs = [float(df[c].corr(total - df[c])) for c in cols]
    fig = _base("Tương quan từng biến với tổng số biến còn lại")
    colors = [GREEN if v >= 0.3 else (GOLD if v >= 0.2 else RED) for v in corrs]
    fig.add_trace(
        go.Bar(
            x=[str(c) for c in cols],
            y=corrs,
            marker_color=colors,
            text=[f"{v:.2f}" for v in corrs],
            textposition="outside",
            hovertemplate="%{x}<br>r = %{y:.3f}<extra></extra>",
        )
    )
    fig.add_hline(y=0.3, line=dict(color=GREEN, dash="dash"), annotation_text="Ngưỡng 0.3")
    fig.update_layout(xaxis_title="Biến quan sát", yaxis_title="Hệ số tương quan", height=330)
    return fig


def scree(variance_table: pd.DataFrame) -> go.Figure | None:
    if variance_table is None or variance_table.empty:
        return None
    labels = [str(i) for i in variance_table.index]
    pct = (
        variance_table.iloc[:, 1]
        if variance_table.shape[1] > 1
        else variance_table.iloc[:, 0]
    ).astype(float)
    fig = _base("Đồ thị scree — phần trăm phương sai giải thích")
    fig.add_trace(
        go.Bar(x=labels, y=pct, marker_color=BLUE, name="% phương sai", text=[f"{v:.1f}%" for v in pct], textposition="outside")
    )
    fig.add_trace(
        go.Scatter(
            x=labels,
            y=pct.cumsum(),
            mode="lines+markers",
            name="Phương sai tích lũy (%)",
            line=dict(color=GOLD, width=3),
        )
    )
    fig.update_layout(xaxis_title="Nhân tố", yaxis_title="Phần trăm (%)")
    return fig


def loadings_heat(loadings: pd.DataFrame) -> go.Figure | None:
    if loadings is None or loadings.empty:
        return None
    z = loadings.to_numpy()
    fig = _base("Ma trận hệ số tải nhân tố (sau xoay)")
    fig.add_trace(
        go.Heatmap(
            z=z,
            x=[str(c) for c in loadings.columns],
            y=[str(i) for i in loadings.index],
            colorscale=[[0, RED], [0.4, "#FFFFFF"], [1, BLUE]],
            zmid=0,
            text=np.round(z, 2),
            texttemplate="%{text}",
            hovertemplate="%{y} → %{x}<br>Hệ số tải: %{z:.3f}<extra></extra>",
        )
    )
    fig.update_layout(height=420)
    return fig


# ---------------------------------------------------------------------------
# 5. Thiết lập & đánh giá hồi quy
# ---------------------------------------------------------------------------
def fitted_vs_actual(df: pd.DataFrame, fit: dict, y: str) -> go.Figure | None:
    yv = pd.to_numeric(fit["y"], errors="coerce") if "y" in fit else None
    if yv is None:
        return None
    fitted = np.asarray(fit["fitted"], dtype=float)
    actual = np.asarray(yv, dtype=float)
    fig = go.Figure()
    fig.add_trace(
        go.Scattergl(
            x=actual,
            y=fitted,
            mode="markers",
            name="Quan sát",
            marker=dict(color=LIGHTBLUE, size=7, opacity=0.8),
            hovertemplate=f"{y} thực tế: %{{x:.2f}}<br>Dự báo: %{{y:.2f}}<extra></extra>",
        )
    )
    lo = float(np.nanmin([actual.min(), fitted.min()]))
    hi = float(np.nanmax([actual.max(), fitted.max()]))
    fig.add_trace(
        go.Scatter(
            x=[lo, hi],
            y=[lo, hi],
            mode="lines",
            name="Đường hoàn hảo (y = x̂)",
            line=dict(color=RED, width=2, dash="dash"),
        )
    )
    fig.update_layout(
        title=dict(
            text=f"Giá trị thực tế và giá trị dự báo của <b>{y}</b>",
            font=dict(size=15, color=BLUE, family=FONT),
        )
    )
    fig.update_xaxes(title_text="Giá trị thực tế")
    fig.update_yaxes(title_text="Giá trị dự báo (fitted)")
    return fig


def resid_vs_fitted(fit: dict) -> go.Figure | None:
    if "residuals" not in fit or "fitted" not in fit:
        return None
    res = np.asarray(fit["residuals"], dtype=float)
    fitted = np.asarray(fit["fitted"], dtype=float)
    fig = go.Figure()
    fig.add_trace(
        go.Scattergl(
            x=fitted,
            y=res,
            mode="markers",
            marker=dict(color=ACCENT, size=7, opacity=0.75),
            hovertemplate="Dự báo: %{x:.2f}<br>Phần dư: %{y:.3f}<extra></extra>",
            name="Phần dư",
        )
    )
    fig.add_hline(y=0, line=dict(color=RED, dash="dash", width=2))
    fig.add_hline(y=float(np.nanmean(res)), line=dict(color=GREEN, dash="dot"))
    fig.update_layout(
        title=dict(
            text="Phần dư theo giá trị dự báo — kiểm tra giả định tính đồng nhất",
            font=dict(size=15, color=BLUE, family=FONT),
        )
    )
    fig.update_xaxes(title_text="Giá trị dự báo (fitted)")
    fig.update_yaxes(title_text="Phần dư (residual)")
    return fig


def resid_hist(fit: dict) -> go.Figure | None:
    if "residuals" not in fit:
        return None
    res = pd.Series(np.asarray(fit["residuals"], dtype=float)).dropna()
    if res.empty:
        return None
    fig = _base("Phân phối phần dư — càng gần đường cong chuẩn càng tốt")
    counts, edges = np.histogram(res, bins=min(30, max(8, int(len(res) ** 0.5))))
    centers = (edges[:-1] + edges[1:]) / 2
    w = edges[1] - edges[0]
    fig.add_trace(
        go.Bar(x=centers, y=counts, width=w, marker_color=LIGHTBLUE, name="Phần dư", opacity=0.85)
    )
    mu, sd = float(res.mean()), float(res.std(ddof=1)) if len(res) > 1 else 1.0
    if sd > 0:
        xs = np.linspace(edges[0], edges[-1], 200)
        pdf = 1 / (sd * np.sqrt(2 * np.pi)) * np.exp(-((xs - mu) ** 2) / (2 * sd**2))
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=pdf * len(res) * w,
                mode="lines",
                name="Đường chuẩn",
                line=dict(color=RED, width=2.5, dash="dash"),
            )
        )
    fig.update_layout(barmode="overlay")
    return fig


def qq_plot(fit: dict) -> go.Figure | None:
    if "residuals" not in fit:
        return None
    res = pd.Series(np.asarray(fit["residuals"], dtype=float)).dropna()
    n = len(res)
    if n < 4:
        return None
    sorted_res = np.sort(res.to_numpy())
    probs = (np.arange(1, n + 1) - 0.5) / n
    from scipy import stats

    theo = stats.norm.ppf(probs)
    slope, intercept = np.polyfit(theo, sorted_res, 1)

    fig = go.Figure()
    fig.add_trace(
        go.Scattergl(
            x=theo,
            y=sorted_res,
            mode="markers",
            marker=dict(color=BLUE, size=7, opacity=0.8),
            name="Phần dư thực nghiệm",
            hovertemplate="Lý thuyết: %{x:.2f}<br>Thực nghiệm: %{y:.3f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=theo,
            y=intercept + slope * theo,
            mode="lines",
            name="Đường chuẩn tham chiếu",
            line=dict(color=RED, width=2.5, dash="dash"),
        )
    )
    fig.update_layout(
        title=dict(
            text="Q-Q plot phần dư — các điểm nằm gần đường chuẩn ⇒ phần dư chuẩn",
            font=dict(size=15, color=BLUE, family=FONT),
        )
    )
    fig.update_xaxes(title_text="Phân phối chuẩn lý thuyết")
    fig.update_yaxes(title_text="Phần dư quan sát")
    return fig