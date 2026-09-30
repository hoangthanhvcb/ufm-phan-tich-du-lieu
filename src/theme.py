"""Giao diện chủ đề UFM (xanh - trắng) cho ứng dụng."""
from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

ASSETS = Path(__file__).resolve().parent.parent / "assets"

# Bảng màu UFM
BLUE = "#0A4D8C"
BLUE_DARK = "#06315E"
BLUE_DEEP = "#04223F"
ACCENT = "#1E88E5"
LIGHT = "#EAF2FB"
WHITE = "#FFFFFF"
GRAY = "#5B6B7C"

UFM_CSS = f"""
<style>
:root {{
  --ufm-blue: {BLUE};
  --ufm-blue-dark: {BLUE_DARK};
  --ufm-blue-deep: {BLUE_DEEP};
  --ufm-accent: {ACCENT};
  --ufm-light: {LIGHT};
}}

/* Nền tổng thể */
.stApp {{
  background: linear-gradient(180deg, #ffffff 0%, #f5f9ff 100%);
}}
html, body, [class*="css"] {{
  font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
}}

/* Ẩn header/footer mặc định để landing đẹp hơn */
header[data-testid="stHeader"] {{
  background: rgba(10, 77, 140, 0.02);
}}

/* Sidebar */
section[data-testid="stSidebar"] {{
  background: linear-gradient(180deg, {BLUE_DARK} 0%, {BLUE_DEEP} 100%);
}}
section[data-testid="stSidebar"] * {{
  color: #ffffff;
}}
section[data-testid="stSidebar"] .stButton > button {{
  background: rgba(255,255,255,0.12);
  color: #ffffff;
  border: 1px solid rgba(255,255,255,0.3);
}}

/* Nút bấm chính */
.stButton > button {{
  background: linear-gradient(135deg, {BLUE} 0%, {ACCENT} 100%);
  color: #ffffff;
  border: none;
  border-radius: 10px;
  padding: 0.55rem 1.4rem;
  font-weight: 600;
  letter-spacing: 0.02em;
  box-shadow: 0 4px 12px rgba(10,77,140,0.25);
  transition: all 0.2s ease;
}}
.stButton > button:hover {{
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(10,77,140,0.35);
  color: #ffffff;
}}
.stButton > button:active {{
  transform: translateY(0);
}}

/* Nút phụ (secondary) */
.stButton > button[kind="secondary"] {{
  background: #ffffff;
  color: {BLUE};
  border: 1px solid {BLUE};
}}

/* Tiêu đề */
h1, h2, h3 {{
  color: {BLUE_DARK};
  letter-spacing: -0.01em;
}}

/* Thẻ card */
.ufm-card {{
  background: #ffffff;
  border: 1px solid #e3edf7;
  border-left: 5px solid {BLUE};
  border-radius: 12px;
  padding: 1.1rem 1.3rem;
  margin: 0.6rem 0;
  box-shadow: 0 2px 10px rgba(10,77,140,0.06);
}}
.ufm-card h4 {{ color: {BLUE_DARK}; margin: 0 0 0.3rem 0; }}
.ufm-card p {{ color: {GRAY}; margin: 0; }}

/* Hero landing */
.ufm-hero {{
  background: linear-gradient(135deg, {BLUE_DEEP} 0%, {BLUE_DARK} 45%, {BLUE} 100%);
  border-radius: 20px;
  padding: 2.6rem 2.2rem;
  color: #ffffff;
  text-align: center;
  margin-bottom: 1.2rem;
  box-shadow: 0 16px 40px rgba(4,34,63,0.35);
}}
.ufm-hero h1 {{
  color: #ffffff;
  font-size: 2.6rem;
  font-weight: 800;
  margin: 0.4rem 0;
  letter-spacing: -0.02em;
}}
.ufm-hero .sub {{
  color: #cfe3f7;
  font-size: 1.15rem;
  margin: 0.3rem 0 0.8rem 0;
}}
.ufm-hero .badge {{
  display: inline-block;
  background: rgba(255,255,255,0.15);
  border: 1px solid rgba(255,255,255,0.3);
  border-radius: 999px;
  padding: 0.3rem 1rem;
  font-size: 0.85rem;
  margin: 0.2rem 0.3rem;
}}

/* Bảng màu thước đo (metric) */
div[data-testid="stMetric"] {{
  background: #ffffff;
  border: 1px solid #e3edf7;
  border-radius: 12px;
  padding: 0.8rem;
  box-shadow: 0 2px 8px rgba(10,77,140,0.05);
}}
div[data-testid="stMetricLabel"] {{ color: {GRAY}; }}
div[data-testid="stMetricValue"] {{ color: {BLUE_DARK}; }}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {{
  gap: 0.3rem;
  background: {LIGHT};
  border-radius: 10px;
  padding: 0.3rem;
}}
.stTabs [data-baseweb="tab"] {{
  border-radius: 8px;
  font-weight: 600;
}}
.stTabs [aria-selected="true"] {{
  background: {BLUE};
  color: #ffffff;
}}

/* Thước tiến trình (progress) */
.stProgress > div > div > div > div {{
  background: linear-gradient(90deg, {BLUE}, {ACCENT});
}}

/* Mã code / phương trình */
.stCode {{ background: {LIGHT}; }}

/* Bảng điểm */
.ufm-score-row {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: {LIGHT};
  border-radius: 8px;
  padding: 0.5rem 0.9rem;
  margin: 0.3rem 0;
  font-weight: 600;
  color: {BLUE_DARK};
}}

/* Nút tiếp tục lớn */
.ufm-next .stButton > button {{
  width: 100%;
  padding: 0.9rem;
  font-size: 1.1rem;
  background: linear-gradient(135deg, {BLUE_DARK}, {BLUE});
}}
</style>
"""


def inject_css() -> None:
    st.markdown(UFM_CSS, unsafe_allow_html=True)


def logo_base64() -> str:
    """Trả về ảnh logo UFM dạng base64 để nhúng HTML."""
    path = ASSETS / "ufm_logo.png"
    if path.exists():
        return base64.b64encode(path.read_bytes()).decode("utf-8")
    return ""


def hero() -> None:
    """Trang chào ấn tượng khi mở ứng dụng."""
    logo = logo_base64()
    logo_html = (
        f'<img src="data:image/png;base64,{logo}" '
        'style="height:72px;margin-bottom:0.4rem;">'
        if logo
        else ""
    )
    st.markdown(
        f"""
        <div class="ufm-hero">
            {logo_html}
            <h1>Phòng thí nghiệm Phân tích Dữ liệu Định lượng</h1>
            <div class="sub">
                Trường Đại học Tài chính – Marketing (UFM) · Phương pháp Nghiên cứu Khoa học
            </div>
            <div>
                <span class="badge">📊 Thống kê mô tả</span>
                <span class="badge">🔍 Cronbach's Alpha</span>
                <span class="badge">🧩 EFA</span>
                <span class="badge">🔗 Tương quan</span>
                <span class="badge">📈 Hồi quy</span>
                <span class="badge">🎮 Trò chơi tương tác QR</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def card(title: str, body: str) -> str:
    return f'<div class="ufm-card"><h4>{title}</h4><p>{body}</p></div>'


def step_badge(index: int, label: str) -> None:
    st.markdown(
        f'<div class="ufm-card" style="border-left-color:{ACCENT};"><h4>Bước {index} · {label}</h4></div>',
        unsafe_allow_html=True,
    )
