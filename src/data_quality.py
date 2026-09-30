"""Kiểm tra tính đầy đủ và nhất quán của dữ liệu."""
from __future__ import annotations

import numpy as np
import pandas as pd


def missing_per_column(df: pd.DataFrame) -> pd.DataFrame:
    """Số ô trống và tỷ lệ thiếu của từng cột."""
    n = len(df)
    missing = df.isna().sum()
    pct = (missing / n * 100).round(2) if n else pd.Series(0, index=df.columns)
    out = pd.DataFrame({"Số ô trống": missing, "Tỷ lệ thiếu (%)": pct})
    out = out[out["Số ô trống"] > 0]
    return out.sort_values("Số ô trống", ascending=False)


def check_completeness(df: pd.DataFrame) -> dict:
    """Kiểm tra tính đầy đủ: ô trống, dòng trùng, cột trống."""
    n_rows, n_cols = df.shape
    total_cells = n_rows * n_cols
    missing_cells = int(df.isna().sum().sum())
    missing_pct = (missing_cells / total_cells * 100) if total_cells else 0.0

    dup_rows = int(df.duplicated().sum())

    # Cột có toàn bộ giá trị thiếu (đã bị loại ở bước đọc, nhưng kiểm tra lại)
    empty_cols = [c for c in df.columns if df[c].isna().all()]

    # Dòng có ít nhất 1 ô trống
    rows_with_missing = int(df.isna().any(axis=1).sum())

    missing_by_col = missing_per_column(df)

    return {
        "n_rows": n_rows,
        "n_cols": n_cols,
        "total_cells": total_cells,
        "missing_cells": missing_cells,
        "missing_pct": round(missing_pct, 2),
        "dup_rows": dup_rows,
        "empty_cols": empty_cols,
        "rows_with_missing": rows_with_missing,
        "missing_by_col": missing_by_col,
    }


def categorical_inconsistencies(series: pd.Series) -> pd.DataFrame:
    """Phát hiện giá trị phân loại không nhất quán (khác chữ hoa/thường, khoảng trắng).

    Ví dụ: "Nam", " nam ", "nam" cùng được chuẩn hóa thành "nam" nhưng ghi khác nhau.
    """
    s = series.astype(str).fillna("<trống>")
    norm = s.str.strip().str.lower()
    grouped = s.groupby(norm).apply(lambda g: sorted(g.unique().tolist()))
    inconsistent = grouped[grouped.apply(len) > 1]
    rows = []
    for key, variants in inconsistent.items():
        rows.append(
            {
                "Chuẩn hóa": key,
                "Số cách viết": len(variants),
                "Các giá trị": ", ".join(variants),
            }
        )
    return pd.DataFrame(rows)


def constant_columns(df: pd.DataFrame) -> list[str]:
    """Cột có giá trị không đổi (chỉ 1 giá trị duy nhất) - ít thông tin."""
    return [c for c in df.columns if df[c].nunique(dropna=True) <= 1]


def numeric_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    """Phát hiện giá trị vô hạn (inf) trong các cột số."""
    num = df.select_dtypes(include="number")
    rows = []
    for c in num.columns:
        inf_count = int(np.isinf(num[c]).sum())
        if inf_count:
            rows.append({"Cột": c, "Số giá trị vô hạn (±inf)": inf_count})
    return pd.DataFrame(rows)


def check_consistency(df: pd.DataFrame) -> dict:
    """Kiểm tra tính nhất quán của dữ liệu."""
    cat_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()

    cat_inconsistencies = {}
    for c in cat_cols:
        res = categorical_inconsistencies(df[c])
        if not res.empty:
            cat_inconsistencies[c] = res

    const_cols = constant_columns(df)
    anomalies = numeric_anomalies(df)
    dup_rows = int(df.duplicated().sum())

    return {
        "cat_inconsistencies": cat_inconsistencies,
        "constant_cols": const_cols,
        "numeric_anomalies": anomalies,
        "dup_rows": dup_rows,
    }


def summarize_quality(completeness: dict, consistency: dict) -> list[dict]:
    """Tổng hợp các vấn đề phát hiện (kèm mức độ) để hiển thị."""
    issues: list[dict] = []

    if completeness["missing_cells"] > 0:
        issues.append(
            {
                "mức": "warning",
                "msg": f"Có {completeness['missing_cells']:,} ô trống ({completeness['missing_pct']}%) trên {completeness['rows_with_missing']} dòng.",
            }
        )
    if completeness["dup_rows"] > 0:
        issues.append(
            {"mức": "warning", "msg": f"Có {completeness['dup_rows']} dòng trùng lặp hoàn toàn."}
        )
    if completeness["empty_cols"]:
        issues.append(
            {"mức": "error", "msg": "Cột trống hoàn toàn: " + ", ".join(completeness["empty_cols"]) + "."}
        )

    if consistency["cat_inconsistencies"]:
        issues.append(
            {
                "mức": "warning",
                "msg": "Giá trị phân loại ghi không nhất quán ở cột: "
                + ", ".join(consistency["cat_inconsistencies"].keys())
                + ".",
            }
        )
    if consistency["constant_cols"]:
        issues.append(
            {"mức": "info", "msg": "Cột có giá trị không đổi: " + ", ".join(consistency["constant_cols"]) + "."}
        )
    if not consistency["numeric_anomalies"].empty:
        issues.append(
            {"mức": "error", "msg": "Cột số chứa giá trị vô hạn (inf)."}
        )

    if not issues:
        issues.append({"mức": "success", "msg": "Dữ liệu đầy đủ và nhất quán, sẵn sàng phân tích."})

    return issues
