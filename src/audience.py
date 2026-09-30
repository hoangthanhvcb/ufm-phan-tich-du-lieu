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


def _client_fingerprint() -> str:
    """Định danh thiết bị ổn định theo IP + User-Agent (phía server).

    Khi cùng một thiết bị quét lại nhiều lần, IP và User-Agent không đổi
    nên id vẫn giữ nguyên (đổi tên cũng không tạo người mới).
    """
    import hashlib

    try:
        ip = st.context.ip_address or ""
    except Exception:
        ip = ""
    try:
        ua = st.context.headers.get("User-Agent") or ""
    except Exception:
        ua = ""
    if not ip and not ua:
        return ""
    return "fp-" + hashlib.md5(f"{ip}|{ua}".encode("utf-8")).hexdigest()[:20]


def get_device_id() -> str:
    """Lấy/cấp mã thiết bị ổn định khi quét lại nhiều lần."""
    import uuid

    # 1) Fingerprint server-side (IP + User-Agent) - ổn định nhất
    fp = _client_fingerprint()
    if fp:
        return fp

    # 2) Fallback: localStorage (best-effort)
    try:
        stored = components.html(_DEVICE_SCRIPT, height=0)
    except Exception:
        stored = None
    if isinstance(stored, str) and stored:
        return stored

    # 3) Fallback cuối: id theo phiên
    if "device_id" not in st.session_state:
        st.session_state["device_id"] = "dev-" + uuid.uuid4().hex[:16]
    return st.session_state["device_id"]


def render_play_view() -> None:
    theme.inject_css()
    qp = st.query_params
    room_id = qp.get("room")

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

    if "rename_mode" not in st.session_state:
        st.session_state["rename_mode"] = False

    if not player_name or st.session_state["rename_mode"]:
        st.markdown(f"Mã phòng: **{room_id}**")
        with st.form("join_form"):
            name = st.text_input(
                "Nhập tên của bạn",
                value=player_name if st.session_state["rename_mode"] else "",
                max_chars=40,
            )
            submitted = st.form_submit_button("✅ Lưu tên")
            if submitted:
                if name.strip():
                    room.register_player(room_id, device_id, name)
                    st.session_state["rename_mode"] = False
                    st.rerun()
                else:
                    st.warning("Vui lòng nhập tên.")
        return

    c_info, c_btn = st.columns([3, 1])
    c_info.success(f"Xin chào **{player_name}**! Bạn đang ở phòng `{room_id}`.")
    if c_btn.button("✏️ Đổi tên", key="rename_btn", use_container_width=True):
        st.session_state["rename_mode"] = True
        st.rerun()

    _live_section(room_id, device_id, player_name)


@st.fragment(run_every=8)
def _live_section(room_id: str, device_id: str, player_name: str) -> None:
    """Khối tự làm mới: hiện câu hỏi của phần hiện tại + bảng điểm."""
    section = room.get_current_section(room_id)

    if not section:
        st.info("⏳ Giảng viên đang chuẩn bị phần tiếp theo...")
        _show_my_scoreboard(room_id, device_id)
        return

    questions = room.get_section_questions(room_id, section)
    section_label = _section_label(section)

    if not questions:
        st.info("Giảng viên chưa công bố câu hỏi cho phần này.")
        return

    # Đã nộp bài cho phần này -> hiện kết quả
    if f"last_score_{section}" in st.session_state:
        sc, tot = st.session_state[f"last_score_{section}"]
        st.success(f"📝 Bạn đã nộp phần **{section_label}**: {sc}/{tot} điểm.")
        _show_my_scoreboard(room_id, device_id)
        return

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
    if st.button("📤 Nộp bài", key=f"play_submit_{section}"):
        score = sum(1 for i, q in enumerate(questions) if answers[i] == q["answer"])
        room.save_score(room_id, section, device_id, player_name, score, len(questions))
        st.session_state[f"last_score_{section}"] = (score, len(questions))
        st.rerun()


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
        st.markdown(theme.leaderboard_html(board), unsafe_allow_html=True)
