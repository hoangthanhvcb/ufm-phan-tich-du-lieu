"""Đọc và chuẩn bị dữ liệu (Bước 1 - Thu thập & chuẩn bị dữ liệu)."""
from __future__ import annotations

import io
import pandas as pd


def read_data(file_bytes: bytes, filename: str) -> pd.DataFrame:
    """Đọc dữ liệu từ CSV hoặc Excel dựa trên phần mở rộng của tên file."""
    name = filename.lower()
    if name.endswith(".csv"):
        for sep in [",", ";", "\t"]:
            try:
                return pd.read_csv(io.BytesIO(file_bytes), sep=sep)
            except Exception:
                continue
        raise ValueError("Không đọc được file CSV. Kiểm tra định dạng file.")
    if name.endswith((".xlsx", ".xlsm")):
        return pd.read_excel(io.BytesIO(file_bytes))
    if name.endswith(".xls"):
        return pd.read_excel(io.BytesIO(file_bytes), engine="xlrd")
    raise ValueError("Định dạng không hỗ trợ. Vui lòng dùng .csv hoặc .xlsx.")


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """Làm sạch cơ bản: bỏ cột hoàn toàn trống, chuẩn hóa tên cột."""
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    df = df.dropna(axis=1, how="all")
    return df


def detect_numeric_columns(df: pd.DataFrame) -> list[str]:
    """Trả về danh sách cột số (numeric) phù hợp để phân tích định lượng."""
    return df.select_dtypes(include="number").columns.tolist()


def detect_categorical_columns(df: pd.DataFrame) -> list[str]:
    """Trả về danh sách cột phân loại (object/category)."""
    return df.select_dtypes(include=["object", "category"]).columns.tolist()


def summarize_data(df: pd.DataFrame) -> dict:
    """Tóm tắt dữ liệu: số dòng, số cột, số cột số, số cột phân loại, % thiếu."""
    total = len(df)
    missing = int(df.isna().sum().sum())
    return {
        "n_rows": total,
        "n_cols": df.shape[1],
        "numeric_cols": detect_numeric_columns(df),
        "categorical_cols": detect_categorical_columns(df),
        "missing_cells": missing,
        "missing_pct": (missing / (total * df.shape[1]) * 100) if total else 0.0,
    }
