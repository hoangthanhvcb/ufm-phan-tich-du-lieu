"""Phân tích tương quan Pearson giữa các biến định lượng."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


def pearson_correlation(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Ma trận hệ số tương quan Pearson giữa các biến."""
    if len(cols) < 2:
        return pd.DataFrame()
    return df[cols].corr(method="pearson").round(4)


def pearson_pvalues(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Ma trận p-value của hệ số tương quan Pearson."""
    n = len(cols)
    out = pd.DataFrame(np.ones((n, n)), index=cols, columns=cols)
    for i, a in enumerate(cols):
        for j, b in enumerate(cols):
            if i == j:
                continue
            sub = df[[a, b]].dropna()
            if len(sub) < 3:
                continue
            _, p = stats.pearsonr(sub[a], sub[b])
            out.loc[a, b] = p
    return out.round(4)


def significant_pairs(
    corr: pd.DataFrame, pvals: pd.DataFrame, alpha: float = 0.05
) -> pd.DataFrame:
    """Liệt kê các cặp biến có tương quan ý nghĩa thống kê (p < alpha)."""
    rows = []
    cols = list(corr.columns)
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            a, b = cols[i], cols[j]
            r = corr.loc[a, b]
            p = pvals.loc[a, b]
            strength = (
                "Rất mạnh" if abs(r) >= 0.8
                else "Mạnh" if abs(r) >= 0.6
                else "Trung bình" if abs(r) >= 0.4
                else "Yếu"
            )
            rows.append(
                {
                    "Biến A": a,
                    "Biến B": b,
                    "Hệ số r": r,
                    "p-value": p,
                    "Ý nghĩa (p<0.05)": p < alpha,
                    "Mức độ": strength,
                }
            )
    return pd.DataFrame(rows).sort_values("Hệ số r", key=abs, ascending=False)
