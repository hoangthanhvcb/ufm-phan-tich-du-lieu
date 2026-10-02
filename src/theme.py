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
@import url('https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@500;600;700;800;900&display=swap');

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

/* Sidebar (nền xanh đậm + chữ trắng) */
section[data-testid="stSidebar"] {{
  background: linear-gradient(180deg, {BLUE_DARK} 0%, {BLUE_DEEP} 100%);
  border-right: 1px solid rgba(255,255,255,0.08);
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
  font-family: 'Be Vietnam Pro', 'Segoe UI', sans-serif;
  font-size: 2.7rem;
  font-weight: 800;
  margin: 0.2rem 0 0.6rem 0;
  letter-spacing: -0.01em;
  line-height: 1.3;
}}
.ufm-hero h1 .highlight {{
  display: block;
  font-weight: 900;
  background: linear-gradient(90deg, #ffffff 0%, #9ec5e8 55%, #7fb3e3 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  color: transparent;
  padding-bottom: 0.15em;
}}
.ufm-hero .topline {{
  font-size: 1.05rem;
  font-weight: 600;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: #9ec5e8;
  margin-bottom: 0.2rem;
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

/* Bảng xếp hạng */
.leaderboard {{
  max-height: 460px;
  overflow-y: auto;
  padding-right: 4px;
}}
/* Trong sidebar: cao vừa phải để 20+ người không đẩy các mục khác ra khỏi màn hình */
[data-testid="stSidebar"] .leaderboard {{
  max-height: 250px;
}}
.leaderboard-more {{
  background: #F5F9FF;
  border-top: 1px dashed #CFE1F3;
  font-style: italic;
}}
.leaderboard-row {{
  display: flex;
  align-items: center;
  gap: 0.5rem;
  background: #ffffff;
  border: 1px solid #e3edf7;
  border-radius: 10px;
  padding: 0.45rem 0.7rem;
  margin: 0.25rem 0;
  font-weight: 600;
  color: {BLUE_DARK} !important;
}}
.leaderboard-row .rank {{
  flex: 0 0 2.2rem;
  text-align: center;
  font-weight: 800;
  color: {BLUE} !important;
  font-size: 0.95rem;
}}
.leaderboard-row .lname {{
  flex: 1;
  text-align: left;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: {BLUE_DARK} !important;
}}
.leaderboard-row .lscore {{
  flex: 0 0 auto;
  font-weight: 800;
  background: {LIGHT};
  border-radius: 999px;
  padding: 0.1rem 0.6rem;
  font-size: 0.9rem;
  color: {BLUE_DARK} !important;
}}
.leaderboard-top1 {{ background: linear-gradient(135deg, #fff8e1, #ffe082); border-color: #f0c674; }}
.leaderboard-top1 .rank {{ color: #c98a00 !important; }}
.leaderboard-top2 {{ background: linear-gradient(135deg, #f3f6fa, #d7e2ee); border-color: #b8c8d8; }}
.leaderboard-top2 .rank {{ color: #7a8ca0 !important; }}
.leaderboard-top3 {{ background: linear-gradient(135deg, #fdf1ec, #f0c4a8); border-color: #d9a07a; }}
.leaderboard-top3 .rank {{ color: #b06a3a !important; }}

/* Nút tiếp tục lớn */
.ufm-next .stButton > button {{
  width: 100%;
  padding: 0.9rem;
  font-size: 1.1rem;
  background: linear-gradient(135deg, {BLUE_DARK}, {BLUE});
}}

/* ------------------------------------------------------------------ */
/* Menu 6 mục trong sidebar                                            */
/* ------------------------------------------------------------------ */
.ufm-menu-title {{
  font-size: 0.72rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #9ec5e8;
  font-weight: 700;
  margin: 0 0 0.5rem 0.4rem;
}}
/* Dòng "Đang xem 3/6" ở sidebar */
.ufm-now {{
  background: linear-gradient(135deg, {BLUE_DEEP}, {BLUE});
  color: #ffffff;
  font-size: 0.88rem;
  font-weight: 700;
  line-height: 1.35;
  padding: 0.55rem 0.7rem;
  border-radius: 12px;
  box-shadow: 0 3px 10px rgba(10,77,140,0.25);
}}
/* Nút chốt buổi học ở cuối phần cuối cùng */
.st-key-ufm_finish_btn button {{
  padding: 0.8rem 1rem;
  font-size: 1.05rem !important;
  font-weight: 800 !important;
  border-radius: 0 !important;
  clip-path: polygon(14px 0, 100% 0, 100% calc(100% - 14px), calc(100% - 14px) 100%, 0 100%, 0 14px);
  box-shadow: 0 10px 26px rgba(10,77,140,0.32) !important;
}}

/* Chữ trong menu 6 mục luôn căn trái */
.st-key-ufm_menu button {{
  justify-content: flex-start !important;
  text-align: left !important;
}}
.st-key-ufm_menu button > div {{
  justify-content: flex-start !important;
  text-align: left !important;
  width: 100%;
}}
section[data-testid="stSidebar"] button[data-testid="stBaseButton-secondary"] {{
  background: transparent !important;
  border: none !important;
  border-left: 3px solid rgba(255,255,255,0.18) !important;
  border-radius: 8px !important;
  color: #d6e6f7 !important;
  text-align: left;
  font-size: 0.88rem;
  font-weight: 600;
  padding: 0.5rem 0.6rem;
  box-shadow: none !important;
  transition: all 0.18s ease;
}}
section[data-testid="stSidebar"] button[data-testid="stBaseButton-secondary"]:hover {{
  background: rgba(255,255,255,0.10) !important;
  border-left-color: #ffffff !important;
  color: #ffffff !important;
  transform: translateX(3px);
}}
section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"] {{
  background: linear-gradient(135deg, rgba(255,255,255,0.22), rgba(255,255,255,0.08)) !important;
  border: 1px solid rgba(255,255,255,0.45) !important;
  border-left: 4px solid #ffffff !important;
  border-radius: 8px !important;
  color: #ffffff !important;
  text-align: left;
  font-size: 0.88rem;
  font-weight: 800;
  padding: 0.5rem 0.6rem;
  box-shadow: none !important;
}}

/* Trạng thái kết nối AI ở đáy menu */
.ufm-ai-status {{
  display: flex;
  align-items: center;
  gap: 0.5rem;
  background: rgba(255,255,255,0.10);
  border: 1px solid rgba(255,255,255,0.22);
  border-radius: 999px;
  padding: 0.4rem 0.8rem;
  margin-top: 0.5rem;
  font-size: 0.82rem;
  font-weight: 700;
  color: #ffffff !important;
}}
.ufm-dot {{
  width: 10px; height: 10px; border-radius: 50%;
  display: inline-block; flex: 0 0 auto;
}}
.ufm-dot.on  {{ background: #22c55e; box-shadow: 0 0 8px #22c55e; }}
.ufm-dot.off {{ background: #ef4444; box-shadow: 0 0 8px #ef4444; }}
.ufm-dot.wait {{ background: #f59e0b; box-shadow: 0 0 8px #f59e0b; }}

/* ------------------------------------------------------------------ */
/* Thanh top: dùng st.button nên bấm để điều hướng được               */
/* ------------------------------------------------------------------ */
.st-key-ufm_topbar {{
  position: sticky;
  top: 0;
  z-index: 999;
  padding: 0.55rem 0.8rem;
  margin-bottom: 0.9rem;
  background: rgba(255,255,255,0.97);
  backdrop-filter: blur(6px);
  border: 1px solid #dce8f5;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(10,77,140,0.10);
}}
.st-key-ufm_topbar button {{
  font-family: 'Be Vietnam Pro', 'Segoe UI', sans-serif;
  font-size: 0.82rem !important;
  font-weight: 600;
  padding: 0.35rem 0.25rem;
  white-space: nowrap;
  border-radius: 999px !important;
  border: 1px solid #dce8f5 !important;
  color: #5B6B7C !important;
  background: #ffffff !important;
  box-shadow: none !important;
  transition: all 0.18s ease;
}}
.st-key-ufm_topbar button:hover {{
  color: {BLUE} !important;
  background: {LIGHT} !important;
  border-color: {BLUE} !important;
}}
.st-key-ufm_topbar button[kind="primary"] {{
  color: #ffffff !important;
  background: linear-gradient(135deg, {BLUE_DARK}, {BLUE}) !important;
  border-color: transparent !important;
  font-weight: 800;
  box-shadow: 0 3px 10px rgba(10,77,140,0.30) !important;
}}

/* ------------------------------------------------------------------ */
/* Nút điều hướng nổi: Back / Home / Next (dọc)                        */
/* ------------------------------------------------------------------ */
.st-key-ufm_float_nav {{
  position: fixed;
  right: 26px;
  bottom: 26px;
  z-index: 1001;
  width: 128px;
  opacity: 0.42;
  transition: opacity 0.25s ease, transform 0.25s ease;
}}
.st-key-ufm_float_nav:hover {{
  opacity: 1.0;
  transform: translateX(-4px);
}}
.st-key-ufm_float_nav .stButton > button {{
  width: 100%;
  font-weight: 700;
  border-radius: 10px;
  padding: 0.5rem 0.4rem;
  font-size: 0.92rem;
  box-shadow: 0 4px 14px rgba(4,34,63,0.28);
}}
.st-key-ufm_float_nav:hover .stButton > button {{ font-weight: 900; }}

/* Nút Play của trò chơi */
.ufm-play .stButton > button {{
  background: linear-gradient(135deg, #E9A23B, #F5B041);
  font-size: 1.05rem;
  font-weight: 800;
  padding: 0.6rem 1.6rem;
}}

/* Nút Bắt đầu cỡ lớn ở trang chủ */
.ufm-start .stButton > button {{
  font-size: 1.5rem;
  font-weight: 900;
  padding: 1.1rem 3rem;
  border-radius: 16px;
  background: linear-gradient(135deg, {BLUE_DEEP} 0%, {BLUE} 55%, {ACCENT} 100%);
  box-shadow: 0 10px 26px rgba(4,34,63,0.35);
}}
.ufm-start .stButton > button:hover {{ transform: scale(1.03); }}
</style>
"""


def inject_css() -> None:
    st.markdown(UFM_CSS, unsafe_allow_html=True)


PHONE_CSS = f"""
<style>
/* --- Đầu câu hỏi: số câu + đồng hồ --- */
.ufm-q-head {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.6rem;
  margin: 0.2rem 0 0.35rem 0;
}}
.ufm-q-badge {{
  background: linear-gradient(135deg, {BLUE_DARK}, {BLUE});
  color: #ffffff;
  font-size: 0.92rem;
  font-weight: 800;
  padding: 0.3rem 0.75rem;
  border-radius: 999px;
  box-shadow: 0 2px 8px rgba(10,77,140,0.25);
}}
.ufm-q-timer {{
  font-size: 1.35rem;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
}}
.ufm-q-sub {{
  color: #7a8ca0;
  font-size: 0.82rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  margin-bottom: 0.3rem;
}}
/* --- Thẻ câu hỏi --- */
.ufm-q-card {{
  background: linear-gradient(150deg, #FFFFFF 0%, {LIGHT} 100%);
  border: 1.5px solid #CFE1F3;
  border-left: 6px solid {BLUE};
  border-radius: 16px;
  padding: 1rem 1.05rem;
  font-size: 1.16rem;
  font-weight: 700;
  line-height: 1.55;
  color: #10314F;
  margin: 0.5rem 0 0.7rem 0;
  box-shadow: 0 4px 14px rgba(10,77,140,0.10);
}}
/* --- Thẻ kết quả phần vừa chơi --- */
.ufm-score-card {{
  background: linear-gradient(140deg, {BLUE_DEEP} 0%, {BLUE} 100%);
  border-radius: 18px;
  padding: 1rem 1.1rem;
  margin: 0.4rem 0 0.6rem 0;
  color: #ffffff;
  text-align: center;
  box-shadow: 0 6px 18px rgba(10,77,140,0.28);
}}
.ufm-score-head {{
  font-size: 0.92rem;
  font-weight: 700;
  opacity: 0.92;
}}
.ufm-score-main {{
  font-size: 2.9rem;
  font-weight: 900;
  line-height: 1.1;
  font-variant-numeric: tabular-nums;
}}
.ufm-score-main span {{ font-size: 1.3rem; opacity: 0.75; font-weight: 700; }}
.ufm-score-total {{
  background: #FFF7E0;
  border: 1.5px solid #F2D98C;
  color: #7A5B00;
  border-radius: 14px;
  padding: 0.65rem 0.9rem;
  text-align: center;
  font-size: 1.02rem;
  margin-bottom: 0.6rem;
}}
/* --- Danh sách các phần đã chơi --- */
.ufm-score-list {{
  background: #FFFFFF;
  border: 1.5px solid #DCE8F5;
  border-radius: 14px;
  padding: 0.8rem 0.95rem;
  margin-bottom: 0.6rem;
}}
.ufm-score-list-t {{
  font-size: 0.8rem;
  font-weight: 800;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: #7a8ca0;
  margin-bottom: 0.45rem;
}}
.ufm-score-list ul {{ list-style: none; margin: 0; padding: 0; }}
.ufm-score-list li {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.6rem;
  font-size: 0.98rem;
  padding: 0.42rem 0;
  border-bottom: 1px dashed #E4EDF6;
}}
.ufm-score-list li:last-child {{ border-bottom: none; }}
.ufm-score-list li span {{ color: #3D4F63; }}
.ufm-score-list li b {{ color: {BLUE}; white-space: nowrap; }}

/* --- Đáp án dạng thẻ bấm được --- */
.st-key-ufm_opts [data-testid="stRadio"] label {{
  border: 1.5px solid #DCE8F5;
  border-radius: 14px;
  background: #ffffff;
  padding: 0.75rem 0.85rem;
  margin-bottom: 0.5rem;
  font-size: 1.02rem;
  font-weight: 600;
  line-height: 1.45;
  box-shadow: 0 1px 4px rgba(10,77,140,0.06);
  transition: all 0.15s ease;
}}
.st-key-ufm_opts [data-testid="stRadio"] label:hover {{
  border-color: {BLUE};
  background: {LIGHT};
  transform: translateX(2px);
}}
.st-key-ufm_opts [data-testid="stRadio"] label:has(input:checked) {{
  border-color: {BLUE};
  background: linear-gradient(135deg, {LIGHT}, #E3F0FF);
  box-shadow: 0 2px 10px rgba(10,77,140,0.16);
}}
.st-key-ufm_opts [data-testid="stRadio"] label:has(input:disabled) {{
  opacity: 0.55;
}}
</style>
"""


def inject_phone_css() -> None:
    """CSS riêng cho giao diện điện thoại (chỉ dùng ở view Play)."""
    st.markdown(PHONE_CSS, unsafe_allow_html=True)


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
            <div class="topline">Phương pháp nghiên cứu khoa học</div>
            <h1>Xử lý và phân tích <span class="highlight">dữ liệu định lượng</span></h1>
            <div>
                <span class="badge">📊 Thống kê mô tả</span>
                <span class="badge">🔍 Cronbach's Alpha</span>
                <span class="badge">🧩 EFA</span>
                <span class="badge">🔗 Tương quan</span>
                <span class="badge">📈 Hồi quy</span>
                <span class="badge">📱 QUIZZ</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def card(title: str, body: str) -> str:
    return f'<div class="ufm-card"><h4>{title}</h4><p>{body}</p></div>'


def leaderboard_html(board: list[dict], top: int = 10) -> str:
    """Bảng xếp hạng co giãn theo số người chơi.

    - Top 3 (đã có điểm) nổi bật, người 0 điểm xếp cuối không huy chương.
    - Chỉ hiện `top` người có điểm cao nhất + dòng "+N người khác".
    - Danh sách trong khối có `max-height` nên 20+ người vẫn vừa ô sidebar.
    """
    if not board:
        return '<div class="leaderboard" style="color:#5B6B7C;">Chưa có người chơi.</div>'

    # Chỉ người đã CÓ ĐIỂM mới được xếp hạng và nhận huy chương
    played = [r for r in board if (r.get("total_score") or 0) > 0]
    not_played = [r for r in board if (r.get("total_score") or 0) <= 0]
    hidden = len(played) - top

    rows = []
    medals = ["🥇", "🥈", "🥉"]
    for i, r in enumerate(played[:top]):
        cls = "leaderboard-row"
        if i == 0:
            cls += " leaderboard-top1"
        elif i == 1:
            cls += " leaderboard-top2"
        elif i == 2:
            cls += " leaderboard-top3"
        medal = medals[i] if i < 3 else ""
        rank = medal if medal else f"{i + 1}"
        rows.append(
            f'<div class="{cls}">'
            f'<span class="rank">{rank}</span>'
            f'<span class="lname">{r["name"]}</span>'
            f'<span class="lscore">{r["total_score"]} điểm</span>'
            f"</div>"
        )

    if hidden > 0:
        rows.append(
            f'<div class="leaderboard-row leaderboard-more">'
            f'<span class="rank">…</span>'
            f'<span class="lname">+{hidden} người khác</span>'
            f'<span class="lscore" style="background:#f1f4f7;color:#7a8ca0;">—</span>'
            f"</div>"
        )

    # Người chơi chưa trả lời (0 điểm) - không xếp hạng
    if not_played:
        shown_zero = not_played[:5]
        for r in shown_zero:
            rows.append(
                f'<div class="leaderboard-row" style="opacity:0.65;">'
                f'<span class="rank" style="color:#9aa7b4;">–</span>'
                f'<span class="lname">{r["name"]}</span>'
                f'<span class="lscore" style="background:#f1f4f7;color:#7a8ca0;">0 điểm</span>'
                f"</div>"
            )
        left = len(not_played) - len(shown_zero)
        if left > 0:
            rows.append(
                f'<div class="leaderboard-row" style="opacity:0.65;">'
                f'<span class="rank" style="color:#9aa7b4;">–</span>'
                f'<span class="lname">+{left} người chưa chơi</span>'
                f'<span class="lscore" style="background:#f1f4f7;color:#7a8ca0;">0 điểm</span>'
                f"</div>"
            )

    return '<div class="leaderboard">' + "".join(rows) + "</div>"


def step_badge(index: int, label: str) -> None:
    st.markdown(
        f'<div class="ufm-card" style="border-left-color:{ACCENT};"><h4>Bước {index} · {label}</h4></div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Thanh top + trạng thái AI + tiêu đề phần
# ---------------------------------------------------------------------------
def ai_status_dot(connected: bool, detail: str = "", pending: bool = False) -> None:
    """Chấm tròn báo trạng thái kết nối AI: xanh = đã gọi thành công, đỏ = lỗi,
    vàng = có key nhưng chưa kiểm tra. Chỉ hiện MỘT dấu chấm."""
    label = detail or ("AI đã kết nối" if connected else "AI chưa kết nối")
    if pending:
        cls = "wait"
    elif connected:
        cls = "on"
    else:
        cls = "off"
    st.markdown(
        f'<div class="ufm-ai-status"><span class="ufm-dot {cls}"></span>'
        f"<span>{label}</span></div>",
        unsafe_allow_html=True,
    )


def section_heading(index: int, total: int, icon: str, label: str) -> None:
    """Tiêu đề lớn của phần đang xem."""
    st.markdown(
        f"""
        <div class="ufm-card" style="border-left-width:6px;border-left-color:{ACCENT};
             padding:1rem 1.3rem;margin-bottom:1rem;">
            <div style="font-size:0.72rem;letter-spacing:0.14em;text-transform:uppercase;
                        color:{GRAY};font-weight:700;">
                PHẦN {index}/{total}
            </div>
            <h3 style="margin:0.2rem 0 0 0;font-size:1.35rem;color:{BLUE_DARK};">
                {icon} {label}
            </h3>
        </div>
        """,
        unsafe_allow_html=True,
    )
