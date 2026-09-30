"""Kiểm định độ tin cậy thang đo bằng hệ số Cronbach's Alpha."""
from __future__ import annotations

import numpy as np
import pandas as pd


def cronbach_alpha(items: pd.DataFrame) -> float:
    """Tính hệ số Cronbach's Alpha cho một tập biến quan sát (các cột)."""
    items = items.dropna()
    if items.shape[0] < 2 or items.shape[1] < 2:
        return float("nan")
    k = items.shape[1]
    item_vars = items.var(ddof=1, axis=0)
    total_var = items.sum(axis=1).var(ddof=1)
    if total_var == 0:
        return float("nan")
    return (k / (k - 1)) * (1 - item_vars.sum() / total_var)


def item_total_correlation(items: pd.DataFrame) -> pd.Series:
    """Hệ số tương quan biến - tổng (hiệu chỉnh)."""
    items = items.dropna()
    result = {}
    for col in items.columns:
        total = items.sum(axis=1)
        others = total - items[col]
        corr = items[col].corr(others)
        result[col] = corr if pd.notna(corr) else np.nan
    return pd.Series(result)


def alpha_if_deleted(items: pd.DataFrame) -> pd.Series:
    """Hệ số Alpha nếu loại từng biến."""
    items = items.dropna()
    result = {}
    for col in items.columns:
        result[col] = cronbach_alpha(items.drop(columns=[col]))
    return pd.Series(result)


def analyze_scale(df: pd.DataFrame, cols: list[str], threshold: float = 0.3) -> dict:
    """Phân tích độ tin cậy thang đo.

    Trả về:
      - alpha: hệ số Cronbach's Alpha chung
      - alpha_if_deleted: Alpha khi loại từng biến
      - item_total_corr: tương quan biến-tổng hiệu chỉnh
      - drop_items: các biến bị đề xuất loại (tương quan biến-tổng < threshold)
      - verdict: kết luận độ tin cậy thang đo
    """
    items = df[cols].dropna()
    alpha = cronbach_alpha(items)
    aif = alpha_if_deleted(items)
    itc = item_total_correlation(items)
    drop_items = [c for c in cols if pd.notna(itc[c]) and itc[c] < threshold]

    if pd.isna(alpha):
        verdict = "Không đủ dữ liệu để tính Alpha."
    elif alpha >= 0.9:
        verdict = "Thang đo rất tốt."
    elif alpha >= 0.8:
        verdict = "Thang đo tốt."
    elif alpha >= 0.7:
        verdict = "Thang đo chấp nhận được."
    elif alpha >= 0.6:
        verdict = "Thang đo cần xem xét lại."
    else:
        verdict = "Thang đo không đạt độ tin cậy."

    summary = pd.DataFrame(
        {
            "Tương quan biến - tổng": itc.round(4),
            "Alpha nếu loại biến": aif.round(4),
        }
    )
    summary["Đề xuất loại"] = summary["Tương quan biến - tổng"] < threshold
    return {
        "alpha": alpha,
        "summary": summary,
        "drop_items": drop_items,
        "verdict": verdict,
        "threshold": threshold,
    }
