"""Trang người chơi (điện thoại) - quét QR để tham gia và trả lời."""
from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

from src import room
from src import theme

_DEVICE_KEY = "ufm_dev_id"

_DEVICE_SCRIPT = """
<script>
(function () {
  const KEY = 'ufm_dev_id';
  let id = null;
  try { id = localStorage.getItem(KEY); } catch (e) {}
  if (!id) {
    id = (window.crypto && crypto.randomUUID)
      ? crypto.randomUUID()
      : 'd' + Date.now() + Math.random().toString(16).slice(2);
    try { localStorage.setItem(KEY, id); } catch (e) {}
  }
  const send = function () {
    if (window.Streamlit && typeof window.Streamlit.setComponentValue === 'function') {
      window.Streamlit.setComponentValue(id);
    } else {
      setTimeout(send, 60);
    }
  };
  send();
})();
</script>
"""


def get_device_id() -> str:
    """Lấy/cấp mã thiết bị từ localStorage (giữ ổn định khi quét QR nhiều lần)."""
    if "device_id" in st.session_state and st.session_state["device_id"]:
        return st.session_state["device_id"]
    device = components.html(_DEVICE_SCRIPT, height=0)
    if isinstance(device, str) and device:
        st.session_state["device_id"] = device
        return device
    return st.session_state.get("device_id")


def render_play_view() -> None:
    theme.inject_css()
    qp = st.query_params
    room_id = qp.get("room")
    section = qp.get("section")

    st.markdown(
        f"""
        <div class="ufm-hero" style="padding:1.4rem 1.2rem;">
            <h1 style="font-size:1.5rem;">🎮 Tham gia trò chơi</h1>
            <div class="sub" style="font-size:0.95rem;">UFM · Phân tích dữ liệu định lượng</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not room_id:
        st.error("Thiếu mã phòng trong liên kết. Hãy quét lại mã QR ở màn hình.")
        return

    device_id = get_device_id()
    if not device_id:
        st.info("Đang khởi tạo phiên...")
        st.stop()

    player_name = room.get_player(room_id, device_id)

    if not player_name:
        st.markdown(f"Mã phòng: **{room_id}**")
        with st.form("join_form"):
            name = st.text_input("Nhập tên của bạn", max_chars=40)
            submitted = st.form_submit_button("✅ Tham gia")
            if submitted:
                if name.strip():
                    room.register_player(room_id, device_id, name)
                    st.rerun()
                else:
                    st.warning("Vui lòng nhập tên.")
        return

    st.success(f"Xin chào **{player_name}**! Bạn đang ở phòng `{room_id}`.")

    if section:
        questions = room.get_section_questions(room_id, section)
        section_label = _section_label(section)
        if questions:
            st.markdown(f"### Câu hỏi · {section_label}")
            st.markdown("Chọn đáp án cho từng câu rồi bấm **Nộp bài**.")
            answers = []
            for i, q in enumerate(questions):
                answers.append(
                    st.radio(
                        f"**{i + 1}. {q['question']}**",
                        list(range(len(q["options"]))),
                        format_func=lambda idx, q=q: q["options"][idx],
                        key=f"play_{section}_{i}",
                    )
                )
            if st.button("📤 Nộp bài", key="play_submit"):
                score = sum(1 for i, q in enumerate(questions) if answers[i] == q["answer"])
                room.save_score(room_id, section, device_id, player_name, score, len(questions))
                st.session_state[f"last_score_{section}"] = (score, len(questions))
                st.rerun()

            if f"last_score_{section}" in st.session_state:
                sc, tot = st.session_state[f"last_score_{section}"]
                st.success(f"Kết quả phần này: **{sc}/{tot}** điểm.")
                _show_my_scoreboard(room_id, device_id)
        else:
            st.info("Giảng viên chưa công bố câu hỏi cho phần này. Hãy chờ và quét lại.")
    else:
        st.markdown("Quét mã QR ở màn hình giảng viên để trả lời từng phần.")
        _show_my_scoreboard(room_id, device_id)


def _section_label(section: str) -> str:
    return {
        "descriptive": "Thống kê mô tả",
        "cronbach": "Cronbach's Alpha",
        "efa": "Phân tích nhân tố (EFA)",
        "correlation": "Tương quan Pearson",
        "regression": "Hồi quy tuyến tính",
    }.get(section, section)


def _show_my_scoreboard(room_id: str, device_id: str) -> None:
    board = room.scoreboard(room_id)
    if board:
        st.markdown("### 🏆 Bảng điểm")
        for r in board:
            st.markdown(
                f'<div class="ufm-score-row"><span>🏅 {r["name"]}</span>'
                f'<span>{r["total_score"]} điểm</span></div>',
                unsafe_allow_html=True,
            )
