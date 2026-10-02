"""Công cụ phân tích dữ liệu định lượng - giao diện UFM (xanh - trắng).

Cấu trúc ứng dụng (6 phần nội dung):
  Trang chủ → 6 phần báo cáo, mỗi phần có biểu đồ, trò chơi QR đếm ngược
  và trợ lý AI sinh code Python/R.

Truy cập người chơi: mã QR sinh tự động → ?view=play&room=<mã>
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from src import ai
from src import audience
from src import charts
from src import correlation
from src import cronbach
from src import intro
from src import podium
from src import data_loader as dl
from src import data_quality as dq
from src import descriptive as desc
from src import efa
from src import game
from src import interpretation
from src import qr
from src import quiz
from src import regression
from src import room
from src import sections
from src import theme

st.set_page_config(
    page_title="UFM · Phân tích dữ liệu định lượng",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

ROOM_FILE = Path(
    os.environ.get("UFM_ROOM_FILE", str(Path(tempfile.gettempdir()) / "ufm_room_id.txt"))
)

DEFAULT_PUBLIC_URL = os.environ.get(
    "APP_URL",
    "https://ufm-phan-tich-du-lieu-p2opx2wfjqhmzk4jkaxgap.streamlit.app",
)


# ---------------------------------------------------------------------------
# Tiện ích chung
# ---------------------------------------------------------------------------
def get_room_id() -> str:
    if "room_id" in st.session_state and st.session_state["room_id"]:
        return st.session_state["room_id"]
    if ROOM_FILE.exists():
        rid = ROOM_FILE.read_text().strip()
        if rid:
            st.session_state["room_id"] = rid
            return rid
    rid = room.new_room()
    ROOM_FILE.write_text(rid)
    st.session_state["room_id"] = rid
    return rid


def _secret_url() -> str:
    try:
        return st.secrets.get("APP_URL") or os.environ.get("APP_URL") or ""
    except Exception:
        return os.environ.get("APP_URL") or ""


def get_origin() -> str:
    env_url = _secret_url()
    if env_url:
        return env_url.rstrip("/")
    return DEFAULT_PUBLIC_URL


def _goto(stage: str, idx: int) -> None:
    st.session_state["stage"] = stage
    st.session_state["step_idx"] = idx
    st.rerun()


def scoreboard_fragment(room_id: str) -> None:
    """Bảng điểm tự làm mới (chỉ làm mới khối này)."""
    board = room.scoreboard(room_id)
    players = room.player_count(room_id)
    st.markdown(f"### 🏆 Bảng điểm trực tiếp · {players} người chơi")
    if not board:
        st.info("Chưa có người chơi. Hãy mời quét mã QR.")
        return
    st.markdown(theme.leaderboard_html(board), unsafe_allow_html=True)


def sidebar_leaderboard(room_id: str) -> None:
    try:
        board = room.scoreboard(room_id)
        players = room.player_count(room_id)
    except Exception:  # noqa: BLE001
        st.caption("Đang tải bảng xếp hạng...")
        return
    st.markdown(f"**🏆 Xếp hạng** · {players} người chơi")
    if not board:
        st.caption("Chưa có người chơi.")
        return
    st.markdown(theme.leaderboard_html(board), unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Menu trái · Thanh top · Nút điều hướng nổi
# ---------------------------------------------------------------------------
def _run_ai_check(ai_cfg: dict) -> None:
    """Gọi thật API kiểm tra rồi lưu kết quả (chỉ Công / Thất bại)."""
    with st.spinner("Đang kiểm tra..."):
        st.session_state["ai_check"] = ai.test_connection(ai_cfg)


def _render_ai_status(ai_cfg: dict) -> None:
    """Dòng trạng thái AI ở đáy sidebar. BẤM VÀO để kiểm tra lại kết nối."""
    if not ai_cfg.get("enabled"):
        st.markdown(
            '<div class="ufm-ai-status"><span class="ufm-dot off"></span>'
            "<span>AI chưa kết nối</span></div>",
            unsafe_allow_html=True,
        )
        return

    state = st.session_state.get("ai_check")  # None | (bool, msg)
    model = ai_cfg.get("model", "")
    if state is None:
        cls, mark = "wait", "Chưa kiểm tra"
    elif state[0]:
        cls, mark = "on", "Đã kết nối"
    else:
        cls, mark = "off", "Thất bại"

    # Dòng trạng thái có chấm màu; nút trong suốt phủ kín để bấm là kiểm tra lại
    with st.container(key="ufm_ai_status_btn"):
        st.markdown(
            f'<div class="ufm-ai-status"><span class="ufm-dot {cls}"></span>'
            f"<span>AI · {model}</span></div>"
            f'<div class="ufm-ai-note">{mark} · bấm để kiểm tra lại</div>',
            unsafe_allow_html=True,
        )
        if st.button("Kiểm tra lại kết nối AI", key="ai_status_click"):
            _run_ai_check(ai_cfg)
            st.rerun()

    if state is not None:
        if state[0]:
            st.success("Kết nối thành công")
        else:
            st.error("Kết nối thất bại")


def render_sidebar_menu(current: str, stage: str, step_idx: int, room_id: str, ai_cfg: dict) -> None:
    """Sidebar chỉ còn: Xếp hạng · Đang xem · (đáy) Reset · Trạng thái AI.
    Điều hướng 6 phần nằm ở thanh trên cùng."""
    with st.sidebar:
        # 1) Xếp hạng luôn nằm trên cùng
        sidebar_leaderboard(room_id)

        # 2) Tiến trình hiện tại (không bấm được, chỉ để biết đang ở đâu)
        if current:
            idx = sections.ORDER.index(current) + 1
            icon, label = sections.SECTIONS[current]
            st.markdown(
                f'<div class="ufm-menu-title">Đang xem {idx}/{len(sections.ORDER)}</div>'
                f'<div class="ufm-now">{icon} {label}</div>',
                unsafe_allow_html=True,
            )

        # 3) Đẩy Reset + AI xuống đáy thanh menu
        st.markdown('<div style="flex:1;min-height:1.2rem"></div>', unsafe_allow_html=True)
        st.markdown("---")

        if st.button("🔄 Reset toàn bộ", key="reset_all_btn", use_container_width=True):
            room.reset_all()
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()

        _render_ai_status(ai_cfg)


def render_top_bar(current: str) -> None:
    """Thanh trên cùng: BẤM VÀO mục nào sẽ nhảy thẳng tới phần đó.
    Hover vào mục sẽ hiện tiêu đề đầy đủ (tooltip của Streamlit)."""
    with st.container(key="ufm_topbar"):
        cols = st.columns(len(sections.ORDER))
        for col, key in zip(cols, sections.ORDER):
            icon, full = sections.SECTIONS[key]
            with col:
                if st.button(
                    f"{icon} {sections.short(key)}",
                    key=f"top_nav_{key}",
                    help=full,
                    use_container_width=True,
                    type="primary" if key == current else "secondary",
                ):
                    _goto("steps", sections.ORDER.index(key))


def _nav_targets(stage: str, step_idx: int) -> tuple:
    n = len(sections.ORDER)
    if stage == "steps":
        prev = ("landing", 0) if step_idx <= 0 else ("steps", step_idx - 1)
        nxt = ("done", 0) if step_idx >= n - 1 else ("steps", step_idx + 1)
        return prev, nxt
    if stage == "done":
        return ("steps", n - 1), None
    if stage == "podium":
        return ("steps", n - 1), None
    return None, None


def render_float_nav(stage: str, step_idx: int) -> None:
    """3 nút dọc: Back / Home / Next — nổi góc phải, mờ đi và đậm lên khi rê chuột."""
    if stage == "landing":
        return
    prev_state, next_state = _nav_targets(stage, step_idx)

    with st.container(key="ufm_float_nav"):
        if prev_state and st.button("⬅️ Back", key="nav_back", use_container_width=True):
            _goto(*prev_state)
        if st.button("🏠 Home", key="nav_home", use_container_width=True):
            _goto("landing", 0)
        if next_state and st.button("Next ➡️", key="nav_next", use_container_width=True):
            _goto(*next_state)


# ---------------------------------------------------------------------------
# Trò chơi: nút Play + đếm ngược đồng bộ web & điện thoại
# ---------------------------------------------------------------------------
@st.fragment(run_every=1)
def web_quiz_fragment(room_id: str, section_key: str, label: str) -> None:
    """Hiển thị câu hỏi đang mở và đồng hồ đếm ngược trên chính trang web."""
    state = quiz.view(room_id, section_key)
    if state["status"] != "running":
        return

    q = state["question"]
    remaining = state["remaining"]
    st.markdown(f"#### Câu {state['q_index'] + 1}/{state['total']} · {label}")
    st.progress(max(0.0, min(1.0, remaining / quiz.PER_QUESTION_SECONDS)))
    color = "#C0392B" if remaining <= 3 else theme.BLUE
    st.markdown(
        f"<div style='text-align:center;font-size:1.7rem;font-weight:800;color:{color};"
        f"margin:0.1rem 0 0.5rem 0;'>⏱️ {remaining:.0f}s</div>",
        unsafe_allow_html=True,
    )
    st.markdown(f"**{q['question']}**")
    letters = "ABCD"
    opts = []
    for i, o in enumerate(q["options"]):
        opts.append(f"<b>{letters[i % 4]}.</b> {o}")
    st.markdown(
        '<div style="font-size:1.02rem;line-height:1.9;">'
        + "<br>".join(opts)
        + "</div>",
        unsafe_allow_html=True,
    )


def render_live_quiz(section_key: str, label: str, questions: list[dict], room_id: str) -> None:
    """QR + nút Play; khi chạy thì câu hỏi hiện cả trên web lẫn điện thoại."""
    st.markdown("### 📱 QUIZZ")
    url = f"{get_origin()}?view=play&room={room_id}"

    left, right = st.columns([1, 2])
    with left:
        st.markdown(qr.qr_html(url), unsafe_allow_html=True)
        st.caption(f"Mã phòng: **{room_id}**")
    with right:
        st.markdown(
            theme.card(
                "Cách tham gia",
                "1. Quét mã QR bằng điện thoại.\n"
                "2. Nhập tên để tham gia.\n"
                f"3. Bấm **Play** để mở {quiz.MAX_QUESTIONS} câu hỏi — mỗi câu có "
                f"{quiz.PER_QUESTION_SECONDS} giây, hiển thị đồng thời trên web và điện thoại.\n"
                f"4. **Cách tính điểm:** trả lời đúng +{quiz.POINTS_CORRECT} điểm, cộng thêm tối đa "
                f"+{quiz.SPEED_BONUS_MAX} điểm thưởng tốc độ — nộp càng nhanh càng nhiều điểm. "
                "Trả lời sai không được điểm.",
            ),
            unsafe_allow_html=True,
        )

    state = quiz.view(room_id, section_key)
    if not questions:
        st.caption("Chưa có câu hỏi cho phần này.")
        return
    if state["status"] == "idle":
        c_play, c_note = st.columns([1, 3])
        with c_play:
            with st.container(key=f"ufm_play_{section_key}"):
                if st.button(
                    "▶ Play", key=f"play_{section_key}", use_container_width=True, type="primary"
                ):
                    quiz.start(room_id, section_key, questions)
                    st.rerun()
        with c_note:
            st.caption(
                "Nhấn **Play** khi đã đủ người chơi quét mã QR. Câu hỏi sẽ hiện trên trang này "
                "và trên điện thoại của các bạn."
            )
    elif state["status"] == "done":
        done_c1, done_c2 = st.columns([1, 3])
        with done_c1:
            if st.button(
                "🔁 Chơi lại", key=f"replay_{section_key}", use_container_width=True
            ):
                quiz.start(room_id, section_key, questions)
                st.rerun()
        with done_c2:
            st.success(f"✅ Đã kết thúc vòng hỏi của phần **{label}**.")
    else:
        stop_c1, stop_c2 = st.columns([1, 3])
        with stop_c1:
            if st.button("⏹ Kết thúc", key=f"stop_{section_key}", use_container_width=True):
                quiz.stop(room_id, section_key)
                st.rerun()
        with stop_c2:
            st.info(f"▶ Đang phát câu {state['q_index'] + 1}/{state['total']}.")

    if state["status"] != "idle":
        st.fragment(web_quiz_fragment, run_every=1)(room_id, section_key, label)

    st.fragment(scoreboard_fragment, run_every=5)(room_id)


# ---------------------------------------------------------------------------
# Ngữ cảnh cho AI
# ---------------------------------------------------------------------------
def _code_context(label: str, df, summary: dict, result: str) -> str:
    return (
        f"TÊN FILE DỮ LIỆU: {st.session_state.get('filename', 'data.csv')}\n"
        f"Số dòng: {len(df)}, số cột: {df.shape[1]}\n"
        f"Tất cả biến trong dữ liệu: {', '.join(df.columns)}\n"
        f"Biến định lượng: {', '.join(summary['numeric_cols']) or 'không có'}\n"
        f"Biến phân loại: {', '.join(summary['categorical_cols']) or 'không có'}\n\n"
        f"KẾT QUẢ PHẦN '{label}':\n{result}"
    )


# ---------------------------------------------------------------------------
# 6 phần nội dung
# ---------------------------------------------------------------------------
def render_overview(df, summary: dict):
    """1. Tổng quan về dữ liệu định lượng (+ nơi tải file lên)."""
    st.subheader("Tổng quan về dữ liệu định lượng")

    if df is None:
        uploaded = st.file_uploader(
            "📂 Chọn file dữ liệu (.csv hoặc .xlsx)", type=["csv", "xlsx", "xls"]
        )
        if uploaded is not None:
            try:
                raw = dl.read_data(uploaded.getvalue(), uploaded.name)
                st.session_state["df"] = dl.clean_data(raw)
                st.session_state["filename"] = uploaded.name
                st.session_state["summary"] = dl.summarize_data(st.session_state["df"])
                st.rerun()
            except Exception as e:  # noqa: BLE001
                st.error(f"Lỗi khi đọc file: {e}")
        st.info("Hãy tải lên bộ dữ liệu để bắt đầu phân tích.")
        return [], "", False

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Số dòng", f"{summary['n_rows']:,}")
    col2.metric("Số cột", summary["n_cols"])
    col3.metric("Biến định lượng", len(summary["numeric_cols"]))
    col4.metric("Biến phân loại", len(summary["categorical_cols"]))

    st.markdown(
        theme.card(
            "Dữ liệu định lượng là gì?",
            "Là dữ liệu được thể hiện bằng các giá trị số để ta có thể đo lường, tính toán "
            "và suy luận xác suất — ví dụ: tuổi, thu nhập, điểm thang đo Likert 5 mức.",
        ),
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns([3, 2])
    with c1:
        if summary["numeric_cols"]:
            chosen = st.selectbox(
                "Chọn biến để xem phân phối", summary["numeric_cols"], key="ov_var"
            )
            charts.show(charts.hist_normal(df, chosen))
    with c2:
        charts.show(charts.type_donut(len(summary["numeric_cols"]), len(summary["categorical_cols"])))

    charts.show(charts.boxplot_numeric(df, summary["numeric_cols"]), key="ov_box")

    with st.expander("👀 Xem trước dữ liệu", expanded=False):
        st.dataframe(df.head(100), use_container_width=True)

    result = (
        f"Số dòng: {summary['n_rows']}\nSố cột: {summary['n_cols']}\n"
        f"Biến định lượng: {', '.join(summary['numeric_cols'])}\n"
        f"Biến phân loại: {', '.join(summary['categorical_cols'])}"
    )
    return game.questions_overview(summary), result, True


def render_cleaning(df, summary: dict):
    """2. Thu thập, mã hoá và làm sạch dữ liệu."""
    st.subheader("Thu thập, mã hoá và làm sạch dữ liệu")

    completeness = dq.check_completeness(df)
    consistency = dq.check_consistency(df)
    issues = dq.summarize_quality(completeness, consistency)

    for issue in issues:
        level = issue["mức"]
        msg = issue["msg"]
        if level == "error":
            st.error(msg)
        elif level == "warning":
            st.warning(msg)
        elif level == "success":
            st.success(msg)
        else:
            st.info(msg)

    q1, q2 = st.columns(2)
    with q1:
        st.markdown("**Tính đầy đủ**")
        c1, c2, c3 = st.columns(3)
        c1.metric("Ô trống", f"{completeness['missing_cells']:,}")
        c2.metric("Dòng trùng lặp", completeness["dup_rows"])
        c3.metric("Dòng có ô trống", completeness["rows_with_missing"])
        if not completeness["missing_by_col"].empty:
            st.dataframe(completeness["missing_by_col"], use_container_width=True)
    with q2:
        st.markdown("**Tính nhất quán**")
        if consistency["cat_inconsistencies"]:
            for col, tbl in consistency["cat_inconsistencies"].items():
                st.markdown(f"*Cột `{col}`:*")
                st.dataframe(tbl, use_container_width=True)
        if consistency["constant_cols"]:
            st.markdown("Cột giá trị không đổi: " + ", ".join(consistency["constant_cols"]))
        if not consistency["numeric_anomalies"].empty:
            st.dataframe(consistency["numeric_anomalies"], use_container_width=True)

    g1, g2 = st.columns(2)
    with g1:
        charts.show(charts.missing_bar(completeness["missing_by_col"]))
    with g2:
        charts.show(charts.missing_matrix(df))

    st.markdown(
        theme.card(
            "Vì sao phải làm sạch dữ liệu?",
            "Dữ liệu thô có thể chứa ô trống, giá trị trùng lặp, chữ viết không thống nhất "
            "(ví dụ “Nam”, “nam”, “ NAM ”) và giá trị vô hạn. Nếu không xử lý, kết quả phân tích "
            "sẽ sai lệch.",
        ),
        unsafe_allow_html=True,
    )

    result = _build_dq_context(completeness, consistency, issues)
    return game.questions_cleaning(completeness, consistency), result, True


def render_descriptive(df, summary: dict):
    """3. Thống kê mô tả và phân tích tương quan."""
    st.subheader("Thống kê mô tả và phân tích tương quan")
    num_cols = summary["numeric_cols"]
    if not num_cols:
        st.info("Cần có biến định lượng.")
        return [], "", False

    tab_desc, tab_corr = st.tabs(["📊 Thống kê mô tả", "🔗 Tương quan Pearson"])
    numeric_desc = None
    cat_freq = None
    chosen_cat = None
    chosen_num: list[str] = []

    with tab_desc:
        if num_cols:
            chosen_num = st.multiselect(
                "Chọn biến định lượng", num_cols, default=num_cols[: min(10, len(num_cols))],
                key="ds_num",
            )
            if chosen_num:
                numeric_desc = desc.descriptive_numeric(df, chosen_num)
                st.dataframe(numeric_desc, use_container_width=True)
                for col in chosen_num[:4]:
                    charts.show(charts.hist_normal(df, col), key=f"ds_h_{col}")
        cat_cols = summary["categorical_cols"]
        if cat_cols:
            chosen_cat = st.selectbox("Chọn biến phân loại", cat_cols, key="ds_cat")
            cat_freq = desc.frequency_table(df, chosen_cat)
            st.dataframe(cat_freq, use_container_width=True)
        else:
            st.info("Không có biến phân loại.")

    corr_mat = None
    pairs = None
    with tab_corr:
        corr_cols = st.multiselect(
            "Chọn các biến để tính tương quan", num_cols,
            default=num_cols[: min(8, len(num_cols))], key="co_cols",
        )
        if len(corr_cols) >= 2:
            corr_mat = correlation.pearson_correlation(df, corr_cols)
            pval_mat = correlation.pearson_pvalues(df, corr_cols)
            pairs = correlation.significant_pairs(corr_mat, pval_mat)
            st.dataframe(corr_mat, use_container_width=True)
            charts.show(charts.corr_heatmap(corr_mat))
            if not pairs.empty:
                st.dataframe(pairs, use_container_width=True)
                r0 = float(pairs.iloc[0].get("r", 0)) if "r" in pairs.columns else None
                p0 = float(pairs.iloc[0].get("p", 1)) if "p" in pairs.columns else None
                charts.show(
                    charts.scatter_reg(df, corr_cols[0], corr_cols[1], r0, p0),
                    key="ds_scatter",
                )
            st.markdown("**Giải thích:** " + interpretation.interpret_correlation(pairs))
        else:
            st.info("Chọn ít nhất 2 biến.")

    questions = game.questions_descriptive(numeric_desc, cat_freq, chosen_cat)
    questions += game.questions_correlation(pairs) if pairs is not None else []
    result = ""
    if numeric_desc is not None:
        result += "Thống kê mô tả:\n" + numeric_desc.to_string()
    if corr_mat is not None:
        result += f"\n\nMa trận tương quan:\n{corr_mat.to_string()}"
    result += (
        f"\n\nBiến định lượng đã chọn: {', '.join(chosen_num) or 'chưa chọn'}"
        f"\nBiến phân loại: {', '.join(summary['categorical_cols']) or 'không có'}"
    )
    return questions, result, True


def render_reliability(df, summary: dict):
    """4. Kiểm định độ tin cậy thang đo và phân tích nhân tố EFA."""
    st.subheader("Kiểm định độ tin cậy thang đo và phân tích nhân tố EFA")
    num_cols = summary["numeric_cols"]
    if not num_cols:
        st.info("Cần có biến định lượng.")
        return [], "", False

    tab_alpha, tab_efa = st.tabs(["🎯 Cronbach's Alpha", "🧩 Phân tích nhân tố EFA"])
    alpha_res = None
    scale_cols: list[str] = []
    efa_res = None
    kmo = None
    n_factors = None
    rotation = ""

    with tab_alpha:
        scale_cols = st.multiselect(
            "Chọn các biến quan sát của thang đo", num_cols, key="rel_cols"
        )
        if len(scale_cols) >= 2:
            alpha_res = cronbach.analyze_scale(df, scale_cols)
            c1, c2 = st.columns([1, 3])
            c1.metric("Cronbach's Alpha", f"{alpha_res['alpha']:.4f}")
            c2.info(alpha_res["verdict"])
            st.dataframe(alpha_res["summary"], use_container_width=True)
            charts.show(charts.item_total_bar(df, scale_cols))
            st.markdown(
                "**Giải thích:** "
                + interpretation.interpret_alpha(
                    alpha_res["alpha"], alpha_res["verdict"], alpha_res["drop_items"]
                )
            )
            for s in interpretation.suggest_improvements_alpha(
                alpha_res["alpha"], alpha_res["drop_items"]
            ):
                st.markdown(f"- {s}")
        else:
            st.info("Chọn ít nhất 2 biến quan sát.")

    with tab_efa:
        efa_cols = st.multiselect("Chọn các biến quan sát", num_cols, key="efa_cols")
        if len(efa_cols) >= 2:
            kmo = efa.run_kmo_bartlett(df[efa_cols])
            k1, k2, k3 = st.columns(3)
            k1.metric("KMO", f"{kmo['kmo']:.4f}")
            k2.metric("Bartlett Chi²", f"{kmo['bartlett_chi2']:.2f}")
            k3.metric("Bartlett p-value", f"{kmo['bartlett_p']:.4f}")

            n_factors = st.slider(
                "Số nhân tố", 1, len(efa_cols), value=min(3, len(efa_cols)), key="efa_n"
            )
            rotation = st.selectbox(
                "Phương pháp xoay",
                ["varimax", "promax", "oblimin", "None"],
                format_func=lambda x: {
                    "varimax": "Varimax (trực giao)",
                    "promax": "Promax (xiên)",
                    "oblimin": "Oblimin (xiên)",
                    "None": "Không xoay",
                }[x],
                key="efa_rot",
            )
            rot = None if rotation == "None" else rotation
            efa_res = efa.run_efa(df[efa_cols], n_factors, rotation=rot)
            st.subheader("Phương sai giải thích")
            st.dataframe(efa_res["variance_table"], use_container_width=True)
            c1, c2 = st.columns(2)
            with c1:
                charts.show(charts.scree(efa_res["variance_table"]))
            with c2:
                charts.show(charts.loadings_heat(efa_res["loadings"]))
            st.subheader("Gán biến vào nhân tố")
            st.dataframe(efa.assign_items_to_factors(efa_res["loadings"]), use_container_width=True)
            st.markdown("**Giải thích:** " + interpretation.interpret_efa(kmo, efa_res["variance_table"]))
        else:
            st.info("Chọn ít nhất 2 biến.")

    questions = []
    if alpha_res:
        questions += game.questions_cronbach(
            alpha_res["alpha"], alpha_res["drop_items"], alpha_res["verdict"]
        )
    if efa_res:
        questions += game.questions_efa(kmo, efa_res["variance_table"], n_factors)

    result = ""
    if alpha_res:
        result += (
            f"Cronbach's Alpha = {alpha_res['alpha']:.4f}. {alpha_res['verdict']}\n"
            f"Biến: {', '.join(scale_cols)}\n"
            f"Đề xuất loại: {alpha_res['drop_items'] or 'không có'}\n"
        )
    if efa_res:
        result += (
            f"\nKMO = {kmo['kmo']:.4f}, Bartlett p = {kmo['bartlett_p']:.4f}\n"
            f"Số nhân tố = {n_factors}, xoay = {rotation}\n"
            f"Biến quan sát: {', '.join(efa_cols)}\n"
            + efa_res["variance_table"].to_string()
        )
    if not result:
        result = "Chưa chọn biến để phân tích."
    return questions, result, True


def render_ols_setup(df, summary: dict):
    """5. Thiết lập mô hình hồi quy OLS."""
    st.subheader("Thiết lập mô hình hồi quy OLS")
    num_cols = summary["numeric_cols"]
    if not num_cols:
        st.info("Cần có biến định lượng.")
        return [], "", False

    dep_var = st.selectbox("Biến phụ thuộc (Y)", num_cols, key="ols_y")
    # Giữ nguyên danh sách lựa chọn để đổi Y không xoá sạch lựa chọn X đang có.
    picked = st.multiselect("Biến độc lập (X)", num_cols, key="ols_x")
    indep_vars = [c for c in picked if c != dep_var]
    if len(picked) != len(indep_vars):
        st.caption(f"Đã bỏ qua `{dep_var}` vì không thể vừa là Y vừa là X.")
    if not indep_vars:
        st.info("Chọn ít nhất một biến độc lập.")
        return [], "", False

    fit = regression.fit_ols(df, dep_var, indep_vars)
    st.session_state["ols_fit"] = {"fit": fit, "y": dep_var, "xs": list(indep_vars)}

    st.markdown("#### Phương trình hồi quy ước lượng")
    st.code(regression.model_equation(fit), language="text")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("R²", f"{fit['r2']:.4f}")
    c2.metric("Adjusted R²", f"{fit['adj_r2']:.4f}")
    c3.metric("F (ANOVA)", f"{fit['f_stat']:.2f}")
    c4.metric("F p-value", f"{fit['f_pvalue']:.4f}")

    st.subheader("Bảng hệ số hồi quy")
    st.dataframe(fit["coefficients"], use_container_width=True)

    charts.show(charts.hist_normal(df, dep_var))
    charts.show(charts.fitted_vs_actual(df, fit, dep_var))

    st.markdown(
        theme.card(
            "Cách đọc mô hình",
            "Trong phương trình Y = β0 + β1·X1 + …, β0 là hệ số cắt (giá trị Y khi mọi X bằng 0), "
            "β là hệ số hồi quy. Nếu p-value của một hệ số < 0.05 thì biến đó có tác động "
            "có ý nghĩa đối với Y.",
        ),
        unsafe_allow_html=True,
    )

    result = (
        f"Biến phụ thuộc (Y) = {dep_var}\n"
        f"Biến độc lập (X) = {', '.join(indep_vars)}\n"
        f"{regression.model_equation(fit)}\n"
        f"R² = {fit['r2']:.4f}, Adjusted R² = {fit['adj_r2']:.4f}, "
        f"F = {fit['f_stat']:.2f}, p = {fit['f_pvalue']:.4f}\n"
        + fit["coefficients"].to_string()
    )
    return game.questions_regression(fit), result, True


def render_ols_eval(df, summary: dict):
    """6. Đánh giá mô hình hồi quy."""
    st.subheader("Đánh giá mô hình hồi quy")
    saved = st.session_state.get("ols_fit")
    if not saved:
        st.warning("⚠️ Chưa có mô hình. Hãy vào phần **Thiết lập mô hình hồi quy OLS** trước.")
        if st.button("➡️ Sang phần Thiết lập OLS", key="go_ols_setup", type="primary"):
            _goto("steps", sections.ORDER.index("ols_setup"))
        return [], "", False

    fit = saved["fit"]
    dep_var = saved["y"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("R²", f"{fit['r2']:.4f}")
    c2.metric("Adjusted R²", f"{fit['adj_r2']:.4f}")
    c3.metric("AIC", f"{fit['aic']:.2f}")
    c4.metric("BIC", f"{fit['bic']:.2f}")

    st.markdown("#### Kiểm tra đa cộng tuyến (VIF)")
    vif_df = fit["vif"].rename("VIF").to_frame()
    vif_df["Đa cộng tuyến (VIF >= 10)"] = vif_df["VIF"] >= 10
    st.dataframe(vif_df, use_container_width=True)

    st.markdown("#### Kiểm định F của mô hình")
    st.info(
        f"F = {fit['f_stat']:.2f}, p = {fit['f_pvalue']:.4f} · "
        f"Số quan sát n = {fit['n_obs']}"
    )

    g1, g2 = st.columns(2)
    with g1:
        charts.show(charts.resid_vs_fitted(fit))
    with g2:
        charts.show(charts.resid_hist(fit))
    charts.show(charts.qq_plot(fit))

    for line in interpretation.interpret_regression(fit):
        st.markdown(f"- {line}")
    for s in interpretation.suggest_improvements_regression(fit):
        st.markdown(f"- {s}")

    st.markdown(
        theme.card(
            "Cách đọc biểu đồ",
            "Nếu các điểm phần dư rải ngẫu nhiên quanh đường 0 và nằm gần đường thẳng trong "
            "Q-Q plot ⇒ giả định phần dư chuẩn của OLS được thoả mãn, mô hình đáng tin cậy.",
        ),
        unsafe_allow_html=True,
    )

    result = (
        f"Mô hình: Y = {dep_var}, X = {', '.join(saved['xs'])}\n"
        f"R² = {fit['r2']:.4f}, Adjusted R² = {fit['adj_r2']:.4f}\n"
        f"F = {fit['f_stat']:.2f}, p = {fit['f_pvalue']:.4f}, AIC = {fit['aic']:.2f}\n"
        "VIF:\n"
        + fit["vif"].to_string()
    )
    return game.questions_ols_eval(fit), result, True


SECTION_RENDERERS = {
    "overview": render_overview,
    "cleaning": render_cleaning,
    "descriptive": render_descriptive,
    "reliability": render_reliability,
    "ols_setup": render_ols_setup,
    "ols_eval": render_ols_eval,
}


# ---------------------------------------------------------------------------
# Ngữ cảnh kiểm tra chất lượng dữ liệu cho AI
# ---------------------------------------------------------------------------
def _build_dq_context(completeness: dict, consistency: dict, issues: list[dict]) -> str:
    lines = [
        f"Số dòng: {completeness['n_rows']}, số cột: {completeness['n_cols']}",
        f"Ô trống: {completeness['missing_cells']} ({completeness['missing_pct']}%)",
        f"Dòng trùng lặp: {completeness['dup_rows']}",
        f"Dòng có ô trống: {completeness['rows_with_missing']}",
    ]
    if not completeness["missing_by_col"].empty:
        lines.append("Cột bị thiếu dữ liệu:\n" + completeness["missing_by_col"].to_string())
    if consistency["cat_inconsistencies"]:
        lines.append("Giá trị phân loại không nhất quán:")
        for col, tbl in consistency["cat_inconsistencies"].items():
            lines.append(f"- Cột {col}: {tbl.to_dict('records')}")
    if consistency["constant_cols"]:
        lines.append("Cột giá trị không đổi: " + ", ".join(consistency["constant_cols"]))
    if not consistency["numeric_anomalies"].empty:
        lines.append("Giá trị vô hạn:\n" + consistency["numeric_anomalies"].to_string())
    lines.append("Các vấn đề phát hiện:")
    for issue in issues:
        lines.append(f"- [{issue['mức']}] {issue['msg']}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Trang ứng dụng
# ---------------------------------------------------------------------------
def render_landing(room_id: str) -> None:
    theme.hero()
    st.markdown(
        theme.card(
            "Hướng dẫn",
            "Chọn 1 trong 6 mục ở thanh bên trái để xem nội dung. Mỗi mục có biểu đồ minh hoạ, "
            "trò chơi QR cho cả lớp và code Python/R do AI sinh sẵn.",
        ),
        unsafe_allow_html=True,
    )

    st.markdown("### 📖 Slide bài nhóm")
    c_btn, c_note = st.columns([1, 3])
    c_btn.link_button(
        "🔲 Phóng to toàn màn hình",
        "https://www.canva.com/design/DAHWBaLveP8/cyOuZSUx3yKO6xa4PTiaUw/view",
        use_container_width=True,
    )
    c_note.caption(
        "Bấm nút để mở slide ở chế độ toàn màn hình, dễ dàng chuyển slide khi thuyết trình."
    )
    components.iframe(
        "https://www.canva.com/design/DAHWBaLveP8/cyOuZSUx3yKO6xa4PTiaUw/view?embed",
        height=520,
    )

    st.markdown("### 🎮 Mời các bạn tham gia trò chơi")
    if "show_join_qr" not in st.session_state:
        st.session_state["show_join_qr"] = False

    if not st.session_state["show_join_qr"]:
        if st.button(
            "📱 Tạo mã QR cho người tham gia", key="join_qr_btn", use_container_width=True
        ):
            st.session_state["show_join_qr"] = True
            st.rerun()
    else:
        join_url = f"{get_origin()}?view=play&room={room_id}"
        left, right = st.columns([1, 2])
        with left:
            st.markdown(qr.qr_html(join_url, size=250), unsafe_allow_html=True)
            st.caption(f"Mã phòng: **{room_id}**")
        with right:
            st.markdown(
                "**Quét mã QR bằng điện thoại** để tham gia. Nhận tên xong, tên các bạn "
                "sẽ hiện ngay ở **bảng xếp hạng** bên trái."
            )

    _c1, _c2, _c3 = st.columns([2, 3, 2])
    with _c2:
        with st.container(key="ufm_start_btn"):
            if st.button("🚀 BẮT ĐẦU", key="start_btn", use_container_width=True, type="primary"):
                _goto("steps", 0)


def presenter_view() -> None:
    room_id = get_room_id()
    ai_cfg = ai.get_config()
    stage = st.session_state.get("stage", "landing")
    step_idx = min(st.session_state.get("step_idx", 0), len(sections.ORDER) - 1)

    current_key = sections.ORDER[step_idx] if stage in ("steps", "done") else None

    render_sidebar_menu(current_key, stage, step_idx, room_id, ai_cfg)
    render_float_nav(stage, step_idx)

    if stage == "landing":
        render_landing(room_id)
        return

    if stage == "podium":
        podium.render(room_id)
        c1, c2 = st.columns(2)
        with c1:
            if st.button("⬅️ Quay lại phần cuối", key="pod_back_btn", use_container_width=True):
                _goto("steps", len(sections.ORDER) - 1)
        with c2:
            if st.button("🔄 Bắt đầu buổi mới", key="pod_restart_btn", use_container_width=True):
                for k in list(st.session_state.keys()):
                    del st.session_state[k]
                st.rerun()
        return

    if stage == "done":
        render_top_bar(current_key)
        theme.hero()
        st.markdown("## 🎉 Hoàn tất quy trình phân tích")
        st.markdown(
            theme.card(
                "Tổng kết",
                "Bạn đã đi qua đủ 6 phần: Tổng quan → Thu thập & Làm sạch → Mô tả & Tương quan "
                "→ Độ tin cậy & EFA → Thiết lập hồi quy → Đánh giá hồi quy.",
            ),
            unsafe_allow_html=True,
        )
        st.fragment(scoreboard_fragment, run_every=5)(room_id)
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🔄 Bắt đầu lại", key="restart_btn", use_container_width=True):
                for k in list(st.session_state.keys()):
                    del st.session_state[k]
                st.rerun()
        with c2:
            if st.button(
                "⬅️ Quay lại phần cuối", key="back_last_btn", use_container_width=True
            ):
                _goto("steps", len(sections.ORDER) - 1)
        return

    # ----- Trang nội dung một phần -----
    df = st.session_state.get("df")
    summary = st.session_state.get("summary")
    if df is not None and summary is None:
        summary = dl.summarize_data(df)
        st.session_state["summary"] = summary

    render_top_bar(current_key)
    st.progress((step_idx + 1) / len(sections.ORDER))
    theme.section_heading(
        step_idx + 1, len(sections.ORDER), sections.icon(current_key), sections.title(current_key)
    )

    # Menu vẫn chuyển được phần kể cả khi chưa tải dữ liệu lên.
    questions, result = [], ""
    if df is None and current_key != "overview":
        st.info("⚠️ Chưa có dữ liệu để phân tích.")
        st.markdown(
            theme.card(
                "Cần dữ liệu trước",
                "Hãy tải file .csv hoặc .xlsx ở phần **Tổ quan về dữ liệu định lượng**, "
                "sau đó quay lại phần này để tiếp tục.",
            ),
            unsafe_allow_html=True,
        )
        if st.button(
            "📂 Sang phần Tổ quan để tải dữ liệu", key="goto_overview", type="primary"
        ):
            _goto("steps", sections.ORDER.index("overview"))
    else:
        questions, result, _ready = SECTION_RENDERERS[current_key](df, summary)

    # ----- QUIZZ + Trợ lý AI: LUÔN hiện, không phụ thuộc tải dữ liệu -----
    qkey = f"questions_{current_key}"
    if questions and qkey not in st.session_state:
        st.session_state[qkey] = game.build_questions(current_key, questions)
    render_live_quiz(
        current_key, sections.title(current_key), st.session_state.get(qkey, []), room_id
    )

    if df is None:
        ai_context = (
            "CHƯA CÓ DỮ LIỆU: người dùng chưa tải file lên. Hãy viết code Python "
            "mẫu giải thích các bước phân tích dữ liệu định lượng (nhập đọc, làm sạch, "
            "thống kê mô tả, kiểm định độ tin cậy Cronbach-alpha, hồi quy OLS) một cách "
            "tổng quát, KHÔNG giả định cột dữ liệu cụ thể."
        )
    else:
        ai_context = _code_context(sections.title(current_key), df, summary, result)
    ai.render_ai_code(sections.title(current_key), ai_context, current_key, ai_cfg)

    # ----- Cuối phần cuối cùng: nút chốt buổi học, sang trang trao giải -----
    if current_key == sections.ORDER[-1]:
        st.markdown("---")
        st.markdown(
            theme.card(
                "🏁 Kết thúc buổi học",
                "Khi đã chấm xong các phần, bấm nút bên dưới để sang trang **tổng kết "
                "cuối cùng** với sân khấu trao giải Nhất – Nhì – Ba cho ba người có điểm "
                "cao nhất qua tất cả các vòng.",
            ),
            unsafe_allow_html=True,
        )
        c_end, c_note = st.columns([1, 2])
        with c_end:
            with st.container(key="ufm_finish_btn"):
                if st.button(
                    "🏁 Kết thúc & trao giải",
                    key="go_podium_btn",
                    type="primary",
                    use_container_width=True,
                ):
                    _goto("podium", 0)
        with c_note:
            st.caption(
                "Tổng điểm = cộng dồn điểm của người chơi qua tất cả các phần đã chơi."
            )


# ---------------------------------------------------------------------------
# Điểm vào
# ---------------------------------------------------------------------------
def main() -> None:
    theme.inject_css()
    if st.query_params.get("view") == "play":
        audience.render_play_view()
        return
    # Màn mở đầu điện ảnh: chỉ vào app sau khi bấm "Chào mừng"
    if not intro.already_seen():
        intro.render()
        return
    presenter_view()


if __name__ == "__main__":
    main()