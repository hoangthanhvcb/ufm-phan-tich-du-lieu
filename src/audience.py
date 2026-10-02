"""Trang người chơi (điện thoại) - quét QR để tham gia và trả lời."""
from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

from src import room
from src import quiz
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


@st.fragment(run_every=1)
def _live_section(room_id: str, device_id: str, player_name: str) -> None:
    """Khối tự làm mới mỗi giây: câu hỏi đang mở + đồng hồ đếm ngược + bảng điểm."""
    section = room.get_current_section(room_id)

    if not section:
        st.info("⏳ Giảng viên đang chuẩn bị phần tiếp theo...")
        _show_my_scoreboard(room_id, device_id)
        return

    state = quiz.view(room_id, section)
    section_label = _section_label(section)

    if state["status"] == "idle":
        st.info("⏳ Chờ giảng viên bấm **Play** để bắt đầu vòng hỏi...")
        _show_my_scoreboard(room_id, device_id)
        return

    if state["status"] == "done":
        _finish_section(room_id, section, section_label, device_id, player_name)
        _show_my_scoreboard(room_id, device_id)
        return

    q = state["question"]
    idx, total = state["q_index"] + 1, state["total"]
    remaining = state["remaining"]

    st.markdown(f"### Câu {idx}/{total} · {section_label}")
    st.progress(max(0.0, min(1.0, remaining / quiz.PER_QUESTION_SECONDS)))
    st.markdown(
        f"<div style='text-align:center;font-size:1.6rem;font-weight:800;color:"
        f"{'#C0392B' if remaining <= 3 else '#0A4D8C'}';margin:0.2rem 0 0.6rem 0;'>"
        f"⏱️ {remaining:.0f}s</div>",
        unsafe_allow_html=True,
    )

    # Mỗi câu chỉ được nộp một lần: khóa gắn theo (phòng, phần, câu) + cờ đã nộp
    # trong phiên của thiết bị này -> không thể spam cộng điểm cùng một câu.
    choice_key = f"ans_{room_id}_{section}_{state['q_index']}"
    submitted_key = f"sent_{choice_key}"
    already_sent = bool(st.session_state.get(submitted_key))

    options = [str(o) for o in q["options"]]
    picked = st.radio(
        f"<b>{q['question']}</b>",
        options,
        key=choice_key,
        disabled=already_sent,
    )
    answer = options.index(picked) if picked in options else -1

    if already_sent:
        st.success("✅ Đã nộp đáp án. Chờ câu tiếp theo…")
        _show_my_scoreboard(room_id, device_id)
        return

    if st.button(
        "📤 Nộp đáp án",
        key=f"submit_{choice_key}",
        use_container_width=True,
        type="primary",
    ):
        _record_answer(room_id, section, state, answer, device_id, player_name)
        st.session_state[submitted_key] = True


def _record_answer(
    room_id: str,
    section: str,
    state: dict,
    answer: int,
    device_id: str,
    player_name: str,
) -> None:
    """Lưu đáp án của câu hiện tại và cộng điểm nếu đúng."""
    key = f"score_{room_id}_{section}"
    score = st.session_state.get(key, 0)
    q = state["question"]
    if q and answer == q.get("answer"):
        score += 1
    st.session_state[key] = score


def _finish_section(
    room_id: str,
    section: str,
    section_label: str,
    device_id: str,
    player_name: str,
) -> None:
    """Kết thúc ván: chốt điểm một lần duy nhất cho phần này."""
    key = f"score_{room_id}_{section}"
    done_key = f"done_{room_id}_{section}"
    total = quiz.MAX_QUESTIONS
    try:
        state = quiz.view(room_id, section)
        total = state.get("total") or total
    except Exception:
        pass
    if st.session_state.get(done_key):
        st.success(
            f"📝 Bạn đã nộp phần **{section_label}**: "
            f"{st.session_state.get(key, 0)}/{total} điểm."
        )
        return
    score = st.session_state.get(key, 0)
    try:
        room.save_score(room_id, section, device_id, player_name, score, total)
    except Exception:
        pass
    st.session_state[done_key] = True
    st.success(f"📝 Hết giờ! Bạn nộp phần **{section_label}**: {score}/{total} điểm.")


def _section_label(section: str) -> str:
    from src.sections import SECTIONS

    return SECTIONS.get(section, (section, section))[1]


def _show_my_scoreboard(room_id: str, device_id: str) -> None:
    board = room.scoreboard(room_id)
    if board:
        st.markdown("### 🏆 Bảng điểm")
        st.markdown(theme.leaderboard_html(board), unsafe_allow_html=True)
