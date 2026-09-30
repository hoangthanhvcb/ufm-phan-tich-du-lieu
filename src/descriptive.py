"""Thống kê mô tả (Bước 2 - Thống kê & phân tích sơ bộ)."""
from __future__ import annotations

import pandas as pd


def descriptive_numeric(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Thống kê mô tả cho các biến định lượng: Mean, SD, Min, Max, Median, N."""
    if not cols:
        return pd.DataFrame()
    sub = df[cols]
    out = pd.DataFrame(
        {
            "Số quan sát (N)": sub.count(),
            "Giá trị trung bình (Mean)": sub.mean(),
            "Độ lệch chuẩn (SD)": sub.std(ddof=1),
            "Giá trị nhỏ nhất (Min)": sub.min(),
            "Giá trị lớn nhất (Max)": sub.max(),
            "Trung vị (Median)": sub.median(),
        }
    )
    return out.round(4)


def frequency_table(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """Bảng tần suất và tỷ lệ % cho một biến phân loại."""
    counts = df[col].value_counts(dropna=False)
    pct = df[col].value_counts(dropna=False, normalize=True) * 100
    out = pd.DataFrame({"Tần suất (n)": counts, "Tỷ lệ (%)": pct})
    out["Tỷ lệ (%)"] = out["Tỷ lệ (%)"].round(2)
    out.index.name = col
    return out
