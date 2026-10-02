"""Màn mở đầu điện ảnh kiểu khung ống chụp góc cạnh, bấm 'Chào mừng' mới vào app."""
from __future__ import annotations

import streamlit as st

from src import theme

_SEEN = "ufm_intro_seen"

INTRO_CSS = """
<style>
@keyframes ufmZoom { 0% { transform: scale(1.14); opacity:0; } 100% { transform: scale(1); opacity:1; } }
@keyframes ufmSweep { 0% { top: -10%; opacity:0; } 12% { opacity:1; } 88% { opacity:1; } 100% { top: 105%; opacity:0; } }
@keyframes ufmBlink { 0%,49% { opacity:1; } 50%,100% { opacity:0.18; } }
@keyframes ufmFloat { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-7px); } }
@keyframes ufmIn { 0% { opacity:0; transform: translateY(14px); } 100% { opacity:1; transform: translateY(0); } }
@keyframes ufmShine { 0% { left: -55%; } 55%, 100% { left: 130%; } }
@keyframes ufmBtnPulse {
  0%, 100% { box-shadow: 0 0 0 1px rgba(111,216,255,0.35), 0 0 26px rgba(63,169,245,0.45), 0 14px 40px rgba(0,0,0,0.5); }
  50% { box-shadow: 0 0 0 1px rgba(111,216,255,0.75), 0 0 46px rgba(87,208,255,0.85), 0 14px 44px rgba(0,0,0,0.55); }
}

.st-key-ufm_intro { padding: 0 0 1rem; }

.ufm-stage {
  position: relative;
  border-radius: 6px;
  background:
    radial-gradient(1200px 420px at 50% -8%, #10365E 0%, transparent 62%),
    linear-gradient(160deg, #04080F 0%, #071324 55%, #03060C 100%);
  border: 1px solid #1D4E80;
  overflow: hidden;
  animation: ufmZoom 1.05s cubic-bezier(.2,.8,.2,1) both;
  font-family: 'Be Vietnam Pro', 'Segoe UI', sans-serif;
}
/* lưới kỹ thuật số */
.ufm-stage::before {
  content: "";
  position: absolute; inset: 0;
  background-image:
    linear-gradient(rgba(63,169,245,0.09) 1px, transparent 1px),
    linear-gradient(90deg, rgba(63,169,245,0.09) 1px, transparent 1px);
  background-size: 38px 38px;
  pointer-events: none;
}
/* vệt sáng quét dọc như máy quét ống chụp */
.ufm-sweep {
  position: absolute; left: 0; right: 0; top: 0;
  height: 130px;
  background: linear-gradient(180deg, transparent, rgba(63,169,245,0.22) 55%, rgba(120,220,255,0.75) 78%, transparent);
  animation: ufmSweep 2.6s linear infinite;
  pointer-events: none;
  z-index: 3;
}
/* khung ống chụp góc cạnh */
.ufm-frame {
  position: relative;
  margin: 2.4rem auto 0;
  width: min(720px, 92%);
  padding: 2.4rem 1.6rem 2rem;
  background: linear-gradient(150deg, rgba(9,25,45,0.96), rgba(4,10,20,0.96));
  border: 1px solid #2E7CC0;
  clip-path: polygon(26px 0, 100% 0, 100% calc(100% - 26px), calc(100% - 26px) 100%, 0 100%, 0 26px);
  box-shadow: 0 0 0 1px rgba(63,169,245,0.15) inset, 0 18px 60px rgba(0,0,0,0.65);
  z-index: 2;
}
/* bốn góc ngắm góc cạnh */
.ufm-frame::before, .ufm-frame::after {
  content: "";
  position: absolute;
  width: 34px; height: 34px;
  border: 3px solid #57D0FF;
}
.ufm-frame::before {
  top: -3px; left: -3px;
  border-right: none; border-bottom: none;
  clip-path: polygon(0 0, 100% 0, 0 100%);
}
.ufm-frame::after {
  bottom: -3px; right: -3px;
  border-left: none; border-top: none;
  clip-path: polygon(100% 0, 100% 100%, 0 100%);
}
.ufm-logo-slot {
  width: 118px; height: 118px;
  margin: -3.9rem auto 0.5rem;
  background: #04101E;
  border: 2px solid #57D0FF;
  clip-path: polygon(50% 0, 100% 25%, 100% 75%, 50% 100%, 0 75%, 0 25%);
  display: flex; align-items: center; justify-content: center;
  animation: ufmFloat 3.4s ease-in-out infinite;
  box-shadow: 0 0 34px rgba(87,208,255,0.45);
}
.ufm-logo-slot img { width: 84px; height: 84px; object-fit: contain; }
.ufm-eyebrow {
  text-align: center;
  color: #57D0FF;
  font-size: 0.74rem;
  font-weight: 800;
  letter-spacing: 0.34em;
  margin-top: 0.5rem;
  text-transform: uppercase;
}
.ufm-hero-title {
  text-align: center;
  font-size: clamp(2.4rem, 7vw, 4.1rem);
  font-weight: 900;
  letter-spacing: 0.05em;
  line-height: 1.08;
  color: #EAF7FF;
  margin: 0.35rem 0 0.15rem 0;
  text-shadow: 0 0 26px rgba(87,208,255,0.55);
}
.ufm-hero-sub {
  text-align: center;
  color: #9FC6E6;
  font-size: clamp(0.86rem, 2.2vw, 1.02rem);
  font-weight: 600;
  letter-spacing: 0.03em;
}
.ufm-hud {
  display: flex;
  justify-content: center;
  flex-wrap: wrap;
  gap: 0.45rem;
  margin-top: 1.15rem;
}
.ufm-hud span {
  border: 1px solid #23547F;
  background: rgba(10,32,58,0.85);
  color: #8FC9F5;
  font-size: 0.66rem;
  font-weight: 700;
  letter-spacing: 0.16em;
  padding: 0.26rem 0.6rem;
  clip-path: polygon(7px 0, 100% 0, 100% calc(100% - 7px), calc(100% - 7px) 100%, 0 100%, 0 7px);
}
.ufm-hud .rec { color: #FF6B6B; border-color: #7A2B2B; animation: ufmBlink 1.4s steps(1) infinite; }
.ufm-foot {
  text-align: center;
  color: #5E86AC;
  font-size: 0.72rem;
  letter-spacing: 0.2em;
  margin: 1.6rem 0 0.2rem 0;
  animation: ufmIn 1s 0.5s both;
}
/* nút Chào mừng: khung góc cạnh + ánh sáng quét + viền phát sáng */
.st-key-ufm_intro_btn { margin-top: 1.4rem; }
.st-key-ufm_intro_btn button {
  position: relative;
  overflow: hidden;
  width: 100%;
  padding: 1.15rem 1.2rem;
  font-size: 1.34rem !important;
  font-weight: 900 !important;
  letter-spacing: 0.2em;
  color: #F3FBFF !important;
  background: linear-gradient(120deg, #0B3D6B 0%, #1276C4 42%, #0B3D6B 100%) !important;
  background-size: 220% 100% !important;
  border: 2px solid #6FD8FF !important;
  border-radius: 0 !important;
  clip-path: polygon(20px 0, 100% 0, 100% calc(100% - 20px), calc(100% - 20px) 100%, 0 100%, 0 20px);
  box-shadow:
    0 0 0 1px rgba(111,216,255,0.35),
    0 0 26px rgba(63,169,245,0.45),
    0 14px 40px rgba(0,0,0,0.5) !important;
  text-shadow: 0 0 18px rgba(150,225,255,0.75);
  animation: ufmBtnPulse 2.8s ease-in-out infinite;
  transition: transform .18s ease, box-shadow .18s ease;
}
/* vệt sáng chạy ngang qua nút */
.st-key-ufm_intro_btn button::after {
  content: "";
  position: absolute;
  top: -40%; bottom: -40%;
  left: -55%;
  width: 42%;
  background: linear-gradient(100deg, transparent, rgba(255,255,255,0.55), transparent);
  transform: skewX(-18deg);
  animation: ufmShine 3.4s ease-in-out infinite;
}
.st-key-ufm_intro_btn button:hover {
  transform: translateY(-3px);
  background-position: 100% 0 !important;
  box-shadow:
    0 0 0 1px rgba(111,216,255,0.6),
    0 0 44px rgba(87,208,255,0.75),
    0 18px 48px rgba(0,0,0,0.55) !important;
  animation-play-state: paused;
}
.st-key-ufm_intro_btn button:active { transform: translateY(0) scale(0.995); }
</style>
"""


def already_seen() -> bool:
    return bool(st.session_state.get(_SEEN))


def mark_seen() -> None:
    st.session_state[_SEEN] = True


def render() -> None:
    """Hiện màn mở đầu; chỉ thoát ra khi bấm nút Chào mừng."""
    logo = theme.logo_base64()
    st.markdown(INTRO_CSS, unsafe_allow_html=True)
    logo_img = (
        f'<img src="data:image/png;base64,{logo}" alt="UFM" />' if logo else "<b>UFM</b>"
    )
    st.markdown(
        f"""
        <div class="ufm-stage">
          <div class="ufm-sweep"></div>
          <div class="ufm-frame">
            <div class="ufm-logo-slot">{logo_img}</div>
            <div class="ufm-eyebrow">Hệ thống phân tích dữ liệu</div>
            <div class="ufm-hero-title">UFM</div>
            <div class="ufm-hero-sub">Ứng dụng phân tích dữ liệu định lượng</div>
            <div class="ufm-hud">
              <span class="rec">● REC</span>
              <span>ISO 800</span>
              <span>24 FPS</span>
              <span>6 MODULES</span>
              <span>QUIZZ READY</span>
            </div>
          </div>
          <div class="ufm-foot">TRƯỜNG ĐẠI HỌC KHOA HỌC TỰ NHIÊN · KHOA TOÁN</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.container(key="ufm_intro_btn"):
        if st.button("👋  CHÀO MỪNG", type="primary", use_container_width=True):
            mark_seen()
            st.rerun()