"""Trang tổng kết cuối cùng: sân khấu nhất - nhì - ba, pháo giấy và kim tuyến rơi."""
from __future__ import annotations

import random

import streamlit as st

from src import room
from src.sections import ORDER

PODIUM_CSS = """
<style>
@keyframes ufmDrop { 0% { transform: translateY(-14vh) rotate(0deg); opacity:0; }
                      8% { opacity:1; }
                      100% { transform: translateY(104vh) rotate(760deg); opacity:0; } }
@keyframes ufmPop { 0% { transform: scale(.6); opacity:0; }
                    60% { transform: scale(1.06); opacity:1; }
                    100% { transform: scale(1); opacity:1; } }
@keyframes ufmGlow { 0%,100% { box-shadow: 0 0 22px rgba(255,196,0,.45); }
                     50% { box-shadow: 0 0 46px rgba(255,214,102,.85); } }

/* Lớp pháo giấy + kim tuyến phủ kín trang */
.ufm-confetti { position: fixed; inset: 0; pointer-events: none; overflow: hidden; z-index: 5; }
.ufm-confetti i {
  position: absolute;
  top: -14vh;
  display: block;
  animation: ufmDrop linear infinite;
  will-change: transform;
}
.ufm-confetti i.ribbon {
  width: 5px;
  height: 46px;
  border-radius: 2px;
  opacity: .95;
}

.st-key-ufm_podium { padding-top: 0.4rem; }

.ufm-award-stage {
  position: relative;
  border-radius: 20px;
  padding: 1.6rem 1.1rem 1.2rem;
  background:
    radial-gradient(900px 320px at 50% 0%, #1B4C81 0%, transparent 60%),
    linear-gradient(180deg, #07182B 0%, #040D18 100%);
  border: 1px solid #26649C;
  box-shadow: 0 18px 50px rgba(0,0,0,0.45);
  font-family: 'Be Vietnam Pro', 'Segoe UI', sans-serif;
  overflow: hidden;
}
.ufm-award-stage::before {
  content: "";
  position: absolute; inset: 0;
  background:
    repeating-conic-gradient(from 0deg at 50% -10%,
      rgba(255,255,255,0.055) 0deg 6deg, transparent 6deg 12deg);
  pointer-events: none;
}
.ufm-curtain {
  text-align: center;
  font-size: 0.76rem;
  font-weight: 800;
  letter-spacing: 0.3em;
  color: #7FD0FF;
  text-transform: uppercase;
}
.ufm-award-title {
  text-align: center;
  font-size: clamp(1.5rem, 4.4vw, 2.3rem);
  font-weight: 900;
  color: #FFFFFF;
  letter-spacing: 0.04em;
  margin: 0.3rem 0 0.1rem 0;
  text-shadow: 0 0 26px rgba(127,208,255,0.6);
}
.ufm-award-sub {
  text-align: center;
  color: #9FC6E6;
  font-size: 0.9rem;
  font-weight: 600;
  margin-bottom: 1.1rem;
}

/* Bậc thang: nhì | nhất | ba */
.ufm-podium { display: flex; align-items: flex-end; justify-content: center; gap: 0.7rem; }
.ufm-step {
  flex: 1 1 0;
  border-radius: 14px 14px 6px 6px;
  padding: 0.7rem 0.5rem 0.6rem;
  text-align: center;
  color: #ffffff;
  animation: ufmPop .6s cubic-bezier(.2,1.4,.4,1) both;
  min-width: 0;
}
.ufm-step.p2 { order: 1; height: 128px; background: linear-gradient(180deg, #B7C6D6, #7C8EA3);
               animation-delay: .18s; }
.ufm-step.p1 { order: 2; height: 188px; background: linear-gradient(180deg, #FFDE7A, #E2A400);
               animation-delay: .06s; animation-name: ufmPop, ufmGlow;
               animation-duration: .6s, 1.9s;
               animation-iteration-count: 1, infinite; }
.ufm-step.p3 { order: 3; height: 100px; background: linear-gradient(180deg, #F0B98A, #B9752F);
               animation-delay: .3s; }
.ufm-step .medal { font-size: 1.9rem; line-height: 1; }
.ufm-step .place { font-size: 0.68rem; font-weight: 800; letter-spacing: 0.2em; opacity: .9; }
.ufm-step .who {
  font-size: clamp(0.86rem, 2.4vw, 1.12rem);
  font-weight: 900;
  line-height: 1.2;
  margin: 0.22rem 0 0.1rem 0;
  overflow-wrap: anywhere;
}
.ufm-step .pts {
  display: inline-block;
  background: rgba(0,0,0,0.24);
  border-radius: 999px;
  padding: 0.16rem 0.6rem;
  font-size: 0.9rem;
  font-weight: 800;
}
.ufm-step.p1 .who { font-size: clamp(1rem, 3vw, 1.4rem); }

/* Bảng xếp hạng đầy đủ */
.ufm-final-table { margin-top: 1.2rem; text-align: left; }
.ufm-final-table .r {
  display: flex; align-items: center; gap: 0.6rem;
  padding: 0.42rem 0.2rem;
  border-bottom: 1px solid rgba(255,255,255,0.08);
  color: #DCEAF7;
  font-size: 0.92rem;
}
.ufm-final-table .r .n { width: 2.1rem; text-align: center; font-weight: 800; color: #7FD0FF; }
.ufm-final-table .r .nm { flex: 1 1 auto; font-weight: 600; overflow-wrap: anywhere; }
.ufm-final-table .r .sc { font-weight: 800; color: #FFD166; white-space: nowrap; }
.ufm-final-table .r .acc { color: #7FA9CC; font-size: 0.82rem; white-space: nowrap; }

.ufm-empty {
  text-align: center;
  color: #C7DDEE;
  font-size: 0.98rem;
  padding: 1.6rem 0.6rem;
  background: rgba(255,255,255,0.06);
  border: 1px dashed rgba(127,208,255,0.4);
  border-radius: 14px;
}
</style>
"""

_COLORS = [
    "#FFD166", "#4EA8DE", "#EF476F", "#06D6A0", "#F78C6B",
    "#B388FF", "#FF9F1C", "#8ECAE6", "#E63946", "#2EC4B6",
]


def confetti_html(pieces: int = 70) -> str:
    """Pháo giấy + kim tuyến rơi, vị trí/nhịp ngẫu nhiên để mỗi lần mở khác nhau."""
    rng = random.Random()
    out = ['<div class="ufm-confetti">']
    for _ in range(pieces):
        ribbon = rng.random() < 0.45
        color = rng.choice(_COLORS)
        left = rng.uniform(0, 100)
        dur = rng.uniform(3.4, 7.0)
        delay = rng.uniform(-7.0, 0.4)
        if ribbon:
            piece = (
                f'<i class="ribbon" style="left:{left:.2f}%;background:{color};'
                f'animation-duration:{dur:.2f}s;animation-delay:{delay:.2f}s;"></i>'
            )
        else:
            w = rng.uniform(6, 12)
            piece = (
                f'<i style="left:{left:.2f}%;width:{w:.1f}px;height:{w:.1f}px;'
                f'background:{color};border-radius:{rng.choice(["0", "50%", "2px"])};'
                f'animation-duration:{dur:.2f}s;animation-delay:{delay:.2f}s;"></i>'
            )
        out.append(piece)
    out.append("</div>")
    return "".join(out)


def _acc(r: dict) -> str:
    q = int(r.get("total_questions") or 0)
    if q <= 0:
        return "—"
    return f"{int(r.get('total_score') or 0)}/{q}"


def podium_html(top: list[dict]) -> str:
    """Bậc thang nhất - nhì - ba. `top` đã sắp xếp giảm dần theo điểm."""
    slots = {1: ("p1", "🥇", "NHẤT"), 2: ("p2", "🥈", "NHÌ"), 3: ("p3", "🥉", "BA")}
    blocks = []
    for place in (2, 1, 3):
        if place > len(top):
            continue
        r = top[place - 1]
        cls, medal, label = slots[place]
        blocks.append(
            f'<div class="ufm-step {cls}">'
            f'<div class="medal">{medal}</div>'
            f'<div class="place">{label}</div>'
            f'<div class="who">{r["name"]}</div>'
            f'<div class="pts">{int(r.get("total_score") or 0)} điểm · {_acc(r)}</div>'
            f"</div>"
        )
    return '<div class="ufm-podium">' + "".join(blocks) + "</div>"


def render(room_id: str) -> None:
    """Trang tổng kết cuối cùng cho buổi học."""
    try:
        board = room.scoreboard(room_id)
    except Exception:  # noqa: BLE001
        board = []

    ranked = [r for r in board if (r.get("total_score") or 0) > 0]
    others = [r for r in board if (r.get("total_score") or 0) <= 0]
    top = ranked[:3]

    st.markdown(PODIUM_CSS, unsafe_allow_html=True)
    st.markdown(confetti_html(), unsafe_allow_html=True)

    done_sections = max((int(r.get("sections_done") or 0) for r in board), default=0)
    st.markdown(
        f"""
        <div class="ufm-award-stage">
          <div class="ufm-curtain">★ Kết thúc buổi học ★</div>
          <div class="ufm-award-title">🏆  TRAO GIẢI NHẤT – NHÌ – BA</div>
          <div class="ufm-award-sub">
            Tổng kết điểm qua {len(ORDER)} phần · {len(board)} người tham gia ·
            {done_sections} vòng đã chơi
          </div>
          {podium_html(top) if top else '<div class="ufm-empty">Chưa có ai ghi điểm trong buổi học này.</div>'}
        </div>
        """,
        unsafe_allow_html=True,
    )

    if ranked:
        rows = []
        for i, r in enumerate(ranked, start=1):
            medal = ["🥇", "🥈", "🥉"][i - 1] if i <= 3 else str(i)
            rows.append(
                f'<div class="r"><span class="n">{medal}</span>'
                f'<span class="nm">{r["name"]}</span>'
                f'<span class="acc">{_acc(r)}</span>'
                f'<span class="sc">{int(r.get("total_score") or 0)} điểm</span></div>'
            )
        st.markdown(
            '<div class="ufm-final-table">'
            '<div style="color:#7FD0FF;font-weight:800;letter-spacing:.14em;'
            'font-size:.74rem;text-transform:uppercase;padding-bottom:.3rem;">'
            "Bảng xếp hạng đầy đủ</div>"
            + "".join(rows)
            + "</div>",
            unsafe_allow_html=True,
        )

    if others:
        st.caption(f"• {len(others)} người tham gia nhưng chưa ghi được điểm nào.")