"""Giải thích kết quả mô hình và đề xuất cải thiện."""
from __future__ import annotations

import pandas as pd


def interpret_alpha(alpha: float, verdict: str, drop_items: list[str]) -> str:
    """Sinh nhận xét cho kết quả Cronbach's Alpha."""
    parts = [f"Hệ số Cronbach's Alpha = {alpha:.4f}. {verdict}"]
    if drop_items:
        parts.append(
            "Các biến có tương quan biến - tổng < ngưỡng 0.3 nên xem xét loại bỏ: "
            + ", ".join(drop_items)
            + "."
        )
    else:
        parts.append("Tất cả biến quan sát đều có tương quan biến - tổng đạt yêu cầu (>= 0.3).")
    return " ".join(parts)


def interpret_efa(kmo: dict, variance_table: pd.DataFrame) -> str:
    """Sinh nhận xét cho kết quả EFA."""
    parts = []
    parts.append(
        f"KMO = {kmo['kmo']:.4f} ({'phù hợp' if kmo['kmo_ok'] else 'không phù hợp'}, "
        f"ngưỡng >= 0.5)."
    )
    parts.append(
        f"Kiểm định Bartlett: Chi² = {kmo['bartlett_chi2']:.2f}, "
        f"p-value = {kmo['bartlett_p']:.4f} "
        f"({'có ý nghĩa' if kmo['bartlett_ok'] else 'không có ý nghĩa'}, ngưỡng < 0.05)."
    )
    cum = variance_table["Phương sai tích lũy (%)"].iloc[-1]
    parts.append(
        f"Tổng phương sai trích giải thích = {cum:.2f}% "
        f"({'đạt' if cum >= 50 else 'chưa đạt'}, ngưỡng khuyến nghị >= 50%)."
    )
    return " ".join(parts)


def suggest_improvements_alpha(alpha: float, drop_items: list[str]) -> list[str]:
    """Đề xuất cải thiện cho thang đo."""
    sugg = []
    if alpha < 0.7:
        sugg.append("Thang đo chưa đạt độ tin cậy (Alpha < 0.7): rà soát lại câu hỏi, diễn đạt rõ nghĩa và tăng số biến quan sát.")
    if drop_items:
        sugg.append("Loại các biến có tương quan biến - tổng < 0.3 rồi chạy lại Cronbach's Alpha.")
    if alpha >= 0.7 and not drop_items:
        sugg.append("Thang đo đạt độ tin cậy, có thể chuyển sang bước phân tích nhân tố (EFA).")
    return sugg


def suggest_improvements_efa(kmo: dict, variance_table: pd.DataFrame) -> list[str]:
    """Đề xuất cải thiện cho EFA."""
    sugg = []
    if not kmo["kmo_ok"]:
        sugg.append("KMO < 0.5: mẫu chưa đủ phù hợp để phân tích nhân tố, cần tăng cỡ mẫu hoặc loại biến có cộng đồng thấp.")
    if not kmo["bartlett_ok"]:
        sugg.append("Bartlett không có ý nghĩa (p >= 0.05): ma trận tương quan gần như đơn vị, dữ liệu chưa phù hợp cho EFA.")
    cum = variance_table["Phương sai tích lũy (%)"].iloc[-1]
    if cum < 50:
        sugg.append("Tổng phương sai trích < 50%: cân nhắc tăng số nhân tố hoặc loại biến tải yếu.")
    return sugg


def interpret_correlation(pairs: pd.DataFrame) -> str:
    """Sinh nhận xét cho ma trận tương quan Pearson."""
    if pairs.empty:
        return "Không có cặp biến nào để phân tích tương quan."
    sig = pairs[pairs["Ý nghĩa (p<0.05)"]]
    if sig.empty:
        return "Không có cặp biến nào có tương quan ý nghĩa thống kê (p < 0.05)."
    top = sig.iloc[0]
    parts = [
        f"Trong {len(sig)} cặp biến có tương quan ý nghĩa thống kê, "
        f"cặp {top['Biến A']} – {top['Biến B']} có tương quan {top['Mức độ'].lower()} nhất (r = {top['Hệ số r']:.4f})."
    ]
    strong = sig[sig["Mức độ"].isin(["Mạnh", "Rất mạnh"])]
    if len(strong) >= 2:
        parts.append(
            "Có nhiều cặp biến tương quan mạnh, cần lưu ý khả năng đa cộng tuyến khi đưa vào hồi quy."
        )
    return " ".join(parts)


def interpret_regression(fit: dict) -> list[str]:
    """Sinh nhận xét cho kết quả hồi quy OLS."""
    lines = []
    lines.append(
        f"Mô hình giải thích được {fit['r2'] * 100:.2f}% biến thiên của biến phụ thuộc "
        f"(R² = {fit['r2']:.4f}, Adjusted R² = {fit['adj_r2']:.4f})."
    )
    if fit["f_pvalue"] < 0.05:
        lines.append(
            f"Kiểm định F có ý nghĩa thống kê (F = {fit['f_stat']:.2f}, p-value = {fit['f_pvalue']:.4f} < 0.05), "
            "mô hình phù hợp tổng thể."
        )
    else:
        lines.append(
            f"Kiểm định F không có ý nghĩa (p-value = {fit['f_pvalue']:.4f} >= 0.05), "
            "các biến độc lập chưa giải thích đáng kể cho biến phụ thuộc."
        )
    return lines


def suggest_improvements_regression(fit: dict) -> list[str]:
    """Đề xuất cải thiện mô hình hồi quy."""
    sugg = []
    coefs = fit["coefficients"].drop(index="Hằng số (β0)", errors="ignore")
    insig = coefs[~coefs["Có ý nghĩa (p<0.05)"]]
    if not insig.empty:
        sugg.append("Các biến chưa có ý nghĩa thống kê (p >= 0.05): " + ", ".join(insig.index) + ". Cân nhắc loại bỏ và chạy lại mô hình.")
    high_vif = fit["vif"][fit["vif"] >= 10]
    if not high_vif.empty:
        sugg.append("Đa cộng tuyến nghiêm trọng (VIF >= 10) ở biến: " + ", ".join(high_vif.index) + ". Cân nhắc loại bỏ hoặc kết hợp biến.")
    if fit["adj_r2"] < 0.3:
        sugg.append("R² điều chỉnh thấp (< 0.3): mô hình có thể thiếu biến quan trọng, xem xét bổ sung biến độc lập.")
    if fit["f_pvalue"] >= 0.05:
        sugg.append("Mô hình không phù hợp tổng thể (F không có ý nghĩa), cần xem lại lý thuyết và lựa chọn biến.")
    if not sugg:
        sugg.append("Mô hình phù hợp: tất cả biến có ý nghĩa, không có đa cộng tuyến nghiêm trọng. Có thể dùng kết quả để diễn giải và ứng dụng.")
    return sugg
