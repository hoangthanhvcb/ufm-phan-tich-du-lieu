"""Phân tích nhân tố khám phá (EFA) - KMO, Bartlett, ma trận nhân tố xoay."""
from __future__ import annotations

import numpy as np
import pandas as pd
from factor_analyzer import FactorAnalyzer
from factor_analyzer.factor_analyzer import calculate_bartlett_sphericity, calculate_kmo


def run_kmo_bartlett(df: pd.DataFrame) -> dict:
    """Tính chỉ số KMO và kiểm định Bartlett."""
    df = df.dropna()
    kmo_all, kmo_model = calculate_kmo(df)
    chi2, p_value = calculate_bartlett_sphericity(df)
    dof = int(df.shape[1] * (df.shape[1] - 1) / 2)
    return {
        "kmo": float(kmo_model),
        "bartlett_chi2": float(chi2),
        "bartlett_p": float(p_value),
        "dof": dof,
        "kmo_ok": kmo_model >= 0.5,
        "bartlett_ok": p_value < 0.05,
    }


def run_efa(
    df: pd.DataFrame,
    n_factors: int,
    rotation: str = "varimax",
    method: str = "principal",
) -> dict:
    """Chạy EFA và trả về hệ số tải nhân tố, phương sai giải thích, cộng đồng.

    rotation: 'varimax' (mặc định), 'promax', 'oblimin', hoặc None.
    method: 'principal' (mặc định), 'ml', 'minres'.
    """
    df = df.dropna()
    fa = FactorAnalyzer(n_factors=n_factors, rotation=rotation, method=method)
    fa.fit(df)

    loadings = pd.DataFrame(
        fa.loadings_,
        index=df.columns,
        columns=[f"Nhân tố {i + 1}" for i in range(n_factors)],
    )

    communalities = pd.DataFrame(
        {"Cộng đồng (Communality)": fa.get_communalities()},
        index=df.columns,
    )

    eigenvalues, variance, cumulative = fa.get_factor_variance()
    variance_table = pd.DataFrame(
        {
            "Giá trị riêng (Eigenvalue)": eigenvalues,
            "Phương sai giải thích (%)": variance * 100,
            "Phương sai tích lũy (%)": cumulative * 100,
        },
        index=[f"Nhân tố {i + 1}" for i in range(n_factors)],
    ).round(4)

    return {
        "loadings": loadings.round(4),
        "communalities": communalities.round(4),
        "variance_table": variance_table,
        "n_factors": n_factors,
        "rotation": rotation,
        "method": method,
    }


def assign_items_to_factors(loadings: pd.DataFrame, threshold: float = 0.5) -> pd.DataFrame:
    """Gán mỗi biến vào nhân tố có hệ số tải lớn nhất (>= threshold)."""
    rows = []
    for item in loadings.index:
        row = loadings.loc[item]
        best = row.abs().idxmax()
        best_val = row[best]
        rows.append(
            {
                "Biến quan sát": item,
                "Nhân tố": best,
                "Hệ số tải": best_val,
                "Đạt ngưỡng (>= {:.2f})".format(threshold): abs(best_val) >= threshold,
            }
        )
    return pd.DataFrame(rows)
