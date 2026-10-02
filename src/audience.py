"""Trang người chơi (điện thoại) - quét QR để tham gia và trả lời."""
from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

from src import room
from src import quiz
from src import theme
from src.sections import ORDER

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
    theme.inject_phone_css()
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
        _show_score_summary(room_id, section_label)
        _show_my_scoreboard(room_id, device_id)
        return

    q = state["question"]
    idx, total = state["q_index"] + 1, state["total"]
    remaining = state["remaining"]
    ratio = max(0.0, min(1.0, remaining / quiz.PER_QUESTION_SECONDS))
    timer_color = "#C0392B" if remaining <= 3 else theme.BLUE

    st.markdown(
        f"""
        <div class="ufm-q-head">
          <span class="ufm-q-badge">📝 Câu {idx}/{total}</span>
          <span class="ufm-q-timer" style="color:{timer_color};">⏱️ {remaining:.0f}s</span>
        </div>
        <div class="ufm-q-sub">{section_label}</div>
        <div class="ufm-q-card">{q["question"]}</div>
        """,
        unsafe_allow_html=True,
    )
    st.progress(ratio)

    # Mỗi câu chỉ được nộp một lần: khóa gắn theo (phòng, phần, câu) + cờ đã nộp
    # trong phiên của thiết bị này -> không thể spam cộng điểm cùng một câu.
    choice_key = f"ans_{room_id}_{section}_{state['q_index']}"
    submitted_key = f"sent_{choice_key}"
    already_sent = bool(st.session_state.get(submitted_key))

    options = [str(o) for o in q["options"]]
    with st.container(key="ufm_opts"):
        picked = st.radio(
            "Chọn đáp án",
            options,
            key=choice_key,
            label_visibility="collapsed",
            disabled=already_sent,
        )
    answer = options.index(picked) if picked in options else -1

    # Chấm điểm ngầm: người chơi KHÔNG được biết đúng/sai hay được bao nhiêu điểm
    # cho tới khi cả phần kết thúc - tránh họ đoán theo điểm của nhau.
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
    """Chấm câu hiện tại. Điểm = đúng/sai + thưởng tốc độ theo thời gian còn lại
    (đo bằng đồng hồ chung của server, không tin đồng hồ của thiết bị).
    Kết quả lưu ngầm, chỉ hiện khi kết thúc cả phần."""
    key = f"score_{room_id}_{section}"
    ck = f"correct_{room_id}_{section}"
    score = st.session_state.get(key, 0)
    correct = st.session_state.get(ck, 0)
    q = state["question"]
    remaining = float(state.get("remaining", 0.0))

    is_correct = bool(q) and answer == q.get("answer")
    if is_correct:
        correct += 1
        score += quiz.points_for(remaining)
    st.session_state[key] = score
    st.session_state[ck] = correct


def _finish_section(
    room_id: str,
    section: str,
    section_label: str,
    device_id: str,
    player_name: str,
) -> None:
    """Kết thúc ván: chốt điểm một lần duy nhất cho phần này và ghi vào lịch sử."""
    key = f"score_{room_id}_{section}"
    done_key = f"done_{room_id}_{section}"
    total = quiz.MAX_QUESTIONS
    try:
        state = quiz.view(room_id, section)
        total = state.get("total") or total
    except Exception:
        pass
    score = st.session_state.get(key, 0)
    correct = st.session_state.get(f"correct_{room_id}_{section}", 0)
    if st.session_state.get(done_key):
        return
    try:
        room.save_score(room_id, section, device_id, player_name, score, total)
    except Exception:
        pass
    st.session_state[done_key] = True
    _record_history(room_id, section, section_label, score, total, correct)


def _record_history(
    room_id: str, section: str, section_label: str, score: int, total: int, correct: int
) -> None:
    """Lưu kết quả từng phần của người chơi để cộng dồn và xem lại."""
    hist_key = f"hist_{room_id}"
    items = [h for h in st.session_state.get(hist_key, []) if h["section"] != section]
    items.append(
        {
            "section": section,
            "label": section_label,
            "score": int(score),
            "total": int(total),
            "correct": int(correct),
            "max": int(total) * quiz.max_points_per_question(),
        }
    )
    st.session_state[hist_key] = items


def _cumulative(room_id: str) -> int:
    """Tổng điểm tích luỹ qua tất cả phần người chơi đã hoàn thành."""
    return sum(int(h["score"]) for h in st.session_state.get(f"hist_{room_id}", []))


def _show_score_summary(room_id: str, section_label: str) -> None:
    """Thẻ tổng kết: điểm của phần vừa chơi + tổng tích luỹ + các phần đã chơi."""
    hist = st.session_state.get(f"hist_{room_id}", [])
    if not hist:
        st.info("⏳ Đã xong phần này, đang chờ phần tiếp theo...")
        return
    last = hist[-1]
    cumulative = _cumulative(room_id)
    head = f"{'🏅' if cumulative > last['score'] else '📝'} Điểm phần **{last['label']}**"
    st.markdown(
        f'<div class="ufm-score-card">'
        f'<div class="ufm-score-head">{head}</div>'
        f'<div class="ufm-score-main">{last["score"]}'
        f'<span>/{last.get("max", last["total"] * quiz.max_points_per_question())}</span></div>'
        f'<div class="ufm-score-sub">'
        f'{last.get("correct", 0)}/{last["total"]} câu đúng · có thưởng tốc độ</div>',
        unsafe_allow_html=True,
    )
    if len(hist) > 1:
        st.markdown(
            f'<div class="ufm-score-total">🏅 Tổng tích luỹ: '
            f'<b>{cumulative} điểm</b> qua {len(hist)} phần</div>',
            unsafe_allow_html=True,
        )
    rows = "".join(
        f'<li><span>{h["label"]}</span>'
        f'<b>{h["score"]} đ</b></li>'
        for h in sorted(hist, key=lambda x: ORDER.index(x["section"]) if x["section"] in ORDER else 99)
    )
    st.markdown(
        f'<div class="ufm-score-list"><div class="ufm-score-list-t">Các phần đã chơi</div>'
        f"<ul>{rows}</ul></div>",
        unsafe_allow_html=True,
    )


def _section_label(section: str) -> str:
    from src.sections import SECTIONS

    return SECTIONS.get(section, (section, section))[1]


def _show_my_scoreboard(room_id: str, device_id: str) -> None:
    """Bảng xếp hạng: chỉ hiện sau khi người chơi đã có điểm, tránh hiện
    huy chương vàng/bạc ngay khi vừa quét mã tham gia."""
    if _cumulative(room_id) <= 0:
        return
    board = room.scoreboard(room_id)
    if board:
        st.markdown("### 🏆 Bảng xếp hạng")
        st.markdown(theme.leaderboard_html(board), unsafe_allow_html=True)
