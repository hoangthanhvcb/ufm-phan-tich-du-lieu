"""Hồi quy tuyến tính đa biến (OLS) - thiết lập, ước lượng và đánh giá mô hình."""
from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.outliers_influence import variance_inflation_factor


def fit_ols(df: pd.DataFrame, y: str, xs: list[str]) -> dict:
    """Ước lượng mô hình OLS: Y = β0 + β1*X1 + ... + βk*Xk + ε.

    Trả về kết quả hồi quy và các chỉ số đánh giá:
      - coefficients: bảng hệ số (β, sai số chuẩn, t, p-value, Beta chuẩn hóa)
      - r2, adj_r2: hệ số xác định
      - f_stat, f_pvalue: kiểm định F (ANOVA)
      - vif: chỉ số đa cộng tuyến cho từng biến độc lập
      - residuals, fitted: phần dư và giá trị dự báo
    """
    sub = df[[y] + xs].dropna()
    X = sm.add_constant(sub[xs].astype(float))
    Y = sub[y].astype(float)
    model = sm.OLS(Y, X).fit()

    # Hệ số và thống kê
    coef_df = pd.DataFrame(
        {
            "Hệ số (β)": model.params,
            "Sai số chuẩn": model.bse,
            "Thống kê t": model.tvalues,
            "p-value": model.pvalues,
        }
    )

    # Hệ số Beta chuẩn hóa
    beta_std = {}
    sy = sub[y].std(ddof=1)
    for c in xs:
        beta_std[c] = model.params[c] * sub[c].std(ddof=1) / sy if sy else np.nan
    beta_std["const"] = np.nan
    coef_df["Beta chuẩn hóa"] = pd.Series(beta_std)

    coef_df["Có ý nghĩa (p<0.05)"] = coef_df["p-value"] < 0.05
    coef_df = coef_df.rename(index={"const": "Hằng số (β0)"})
    coef_df = coef_df.round(4)

    # VIF
    vif = pd.Series(
        [
            variance_inflation_factor(X.values, i)
            for i in range(1, X.shape[1])  # bỏ cột hằng số
        ],
        index=xs,
    ).round(4)

    return {
        "y": y,
        "xs": xs,
        "n_obs": int(model.nobs),
        "coefficients": coef_df,
        "r2": float(model.rsquared),
        "adj_r2": float(model.rsquared_adj),
        "f_stat": float(model.fvalue),
        "f_pvalue": float(model.f_pvalue),
        "vif": vif,
        "residuals": model.resid,
        "fitted": model.fittedvalues,
        "aic": float(model.aic),
        "bic": float(model.bic),
    }


def model_equation(fit: dict) -> str:
    """Sinh chuỗi phương trình hồi quy dạng văn bản."""
    coefs = fit["coefficients"]
    b0 = coefs.loc["Hằng số (β0)", "Hệ số (β)"]
    terms = []
    for x in fit["xs"]:
        b = coefs.loc[x, "Hệ số (β)"]
        terms.append(f"{b:+.4f}*{x}")
    return f"{fit['y']} = {b0:.4f} {' '.join(terms)} + ε"
