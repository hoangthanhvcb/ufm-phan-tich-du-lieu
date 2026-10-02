"""Danh mục 6 phần nội dung của báo cáo nghiên cứu khoa học."""
from __future__ import annotations

# key -> (biểu tượng, tiêu đề hiển thị đầy đủ)
SECTIONS: dict[str, tuple[str, str]] = {
    "overview": ("📋", "Tổng quan về dữ liệu định lượng"),
    "cleaning": ("🧹", "Thu thập, mã hoá và làm sạch dữ liệu"),
    "descriptive": ("📊", "Thống kê mô tả và phân tích tương quan"),
    "reliability": ("🎯", "Kiểm định độ tin cậy thang đo và phân tích nhân tố EFA"),
    "ols_setup": ("📈", "Thiết lập mô hình hồi quy OLS"),
    "ols_eval": ("✅", "Đánh giá mô hình hồi quy"),
}

# Thứ tự hiển thị
ORDER: list[str] = list(SECTIONS.keys())


def icon(key: str) -> str:
    return SECTIONS.get(key, ("•", key))[0]


def title(key: str) -> str:
    return SECTIONS.get(key, ("•", key))[1]


def short(key: str) -> str:
    """Tiêu đề rút gọn cho thanh top."""
    return {
        "overview": "Tổng quan",
        "cleaning": "Thu thập & Làm sạch",
        "descriptive": "Mô tả & Tương quan",
        "reliability": "Độ tin cậy & EFA",
        "ols_setup": "Hồi quy OLS",
        "ols_eval": "Đánh giá hồi quy",
    }.get(key, key)