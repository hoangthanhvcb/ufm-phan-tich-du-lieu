"""Công cụ phân tích dữ liệu định lượng - giao diện UFM (xanh - trắng).

Luồng wizard:
  Landing → Tải file → Kiểm tra dữ liệu → từng bước phân tích
  (mỗi bước có trò chơi QR cho nhiều thiết bị tham gia và tính điểm).

Truy cập người chơi: thêm ?view=play&room=<mã>&section=<bước> vào URL
(được sinh tự động thành mã QR ở từng bước).
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from src import data_loader as dl
from src import descriptive as desc
from src import cronbach
from src import efa
from src import correlation
from src import regression
from src import interpretation
from src import data_quality as dq
from src import game
from src import ai
from src import room
from src import qr
from src import audience
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
STEPS = [
    ("descriptive", "Thống kê mô tả", 2),
    ("cronbach", "Cronbach's Alpha", 3),
    ("efa", "Phân tích nhân tố (EFA)", 4),
    ("correlation", "Tương quan Pearson", 5),
    ("regression", "Hồi quy tuyến tính", 6),
]


# ---------------------------------------------------------------------------
# Tiện ích
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


def reset_room() -> None:
    rid = room.new_room()
    ROOM_FILE.write_text(rid)
    st.session_state["room_id"] = rid


DEFAULT_PUBLIC_URL = os.environ.get(
    "APP_URL",
    "https://ufm-phan-tich-du-lieu-p2opx2wfjqhmzk4jkaxgap.streamlit.app",
)


def _secret_url() -> str:
    try:
        return st.secrets.get("APP_URL") or os.environ.get("APP_URL") or ""
    except Exception:
        return os.environ.get("APP_URL") or ""


def get_origin() -> str:
    # 1) Người dùng đã nhập tay ở sidebar
    if st.session_state.get("origin"):
        return st.session_state["origin"]
    # 2) Secret / biến môi trường APP_URL
    env_url = _secret_url()
    if env_url:
        return env_url.rstrip("/")
    # 3) URL app đã deploy
    return DEFAULT_PUBLIC_URL


def scoreboard_fragment(room_id: str) -> None:
    """Bảng điểm tự làm mới (chỉ làm mới khối này)."""
    board = room.scoreboard(room_id)
    players = room.player_count(room_id)
    st.markdown(f"### 🏆 Bảng điểm trực tiếp · {players} người chơi")
    if not board:
        st.info("Chưa có người chơi. Hãy mời quét mã QR.")
        return
    import pandas as pd

    df = pd.DataFrame(board)
    if "device_id" in df.columns:
        df = df.drop(columns=["device_id"])
    df = df.rename(
        columns={
            "name": "Người chơi",
            "total_score": "Tổng điểm",
            "total_questions": "Số câu",
            "sections_done": "Số phần",
        }
    )
    st.dataframe(df, use_container_width=True, hide_index=True)


def sidebar_leaderboard(room_id: str) -> None:
    """Bảng xếp hạng người chơi trong sidebar (tự sắp xếp điểm cao → thấp, tự làm mới)."""
    try:
        board = room.scoreboard(room_id)
        count = room.player_count(room_id)
    except Exception:  # noqa: BLE001
        st.caption("Đang tải bảng xếp hạng...")
        return
    st.markdown("### 🏆 Bảng xếp hạng")
    st.caption(f"{count} người chơi · sắp xếp theo điểm từ cao xuống thấp")
    if not board:
        st.caption("Chưa có người chơi. Mời quét mã QR.")
        return
    medals = ["🥇", "🥈", "🥉"]
    for i, r in enumerate(board):
        medal = medals[i] if i < 3 else f"{i + 1}."
        st.markdown(
            f'<div class="ufm-score-row">'
            f'<span>{medal} {r["name"]}</span>'
            f'<span><b>{r["total_score"]}</b> điểm</span>'
            f"</div>",
            unsafe_allow_html=True,
        )


def render_live_quiz(section_key: str, step_label: str, questions: list[dict], room_id: str) -> None:
    """Lưu câu hỏi, đặt phần hiện tại, hiện QR duy nhất + bảng điểm."""
    if not questions:
        return
    room.save_section_questions(room_id, section_key, questions)
    room.set_current_section(room_id, section_key)
    url = f"{get_origin()}?view=play&room={room_id}"

    st.markdown("### 📱 Trò chơi tương tác")
    left, right = st.columns([1, 2])
    with left:
        st.markdown(qr.qr_html(url), unsafe_allow_html=True)
        st.caption(f"Mã phòng: **{room_id}**")
        st.caption(f"Phần hiện tại: {step_label}")
    with right:
        st.markdown(
            theme.card(
                "Cách tham gia",
                "1. Quét mã QR bằng điện thoại.\n2. Nhập tên để tham gia.\n"
                "3. Trả lời câu hỏi — điểm cộng dồn qua từng phần.",
            ),
            unsafe_allow_html=True,
        )
        st.markdown(
            theme.card(
                "Câu hỏi trên màn hình",
                "Các câu hỏi bên dưới cũng hiển thị trên điện thoại người chơi.",
            ),
            unsafe_allow_html=True,
        )

    # Bảng điểm tự làm mới
    st.fragment(scoreboard_fragment, run_every=5)(room_id)

    # Máy chiếu cũng có thể trả lời (điểm riêng)
    game.render_quiz(step_label, questions, f"quiz_{section_key}")


# ---------------------------------------------------------------------------
# Các bước phân tích
# ---------------------------------------------------------------------------
def step_descriptive(df, summary) -> tuple[list[dict], str]:
    st.subheader("Thống kê mô tả")
    tab_num, tab_cat = st.tabs(["Biến định lượng", "Biến phân loại"])
    numeric_desc = None
    cat_freq = None
    chosen_cat = None
    with tab_num:
        num_cols = summary["numeric_cols"]
        if num_cols:
            chosen_num = st.multiselect(
                "Chọn biến định lượng", num_cols, default=num_cols[: min(10, len(num_cols))]
            )
            if chosen_num:
                numeric_desc = desc.descriptive_numeric(df, chosen_num)
                st.dataframe(numeric_desc, use_container_width=True)
        else:
            st.info("Không có biến định lượng.")
    with tab_cat:
        cat_cols = summary["categorical_cols"]
        if cat_cols:
            chosen_cat = st.selectbox("Chọn biến phân loại", cat_cols)
            cat_freq = desc.frequency_table(df, chosen_cat)
            st.dataframe(cat_freq, use_container_width=True)
        else:
            st.info("Không có biến phân loại.")

    data_qs = game.questions_descriptive(numeric_desc, cat_freq, chosen_cat)
    ctx = "Thống kê mô tả:\n" + (numeric_desc.to_string() if numeric_desc is not None else "")
    if cat_freq is not None:
        ctx += f"\n\nTần suất '{chosen_cat}':\n" + cat_freq.to_string()
    return data_qs, ctx


def step_cronbach(df, summary) -> tuple[list[dict], str, bool]:
    st.subheader("Kiểm định độ tin cậy thang đo")
    num_cols = summary["numeric_cols"]
    if not num_cols:
        st.info("Cần có biến định lượng.")
        return [], "", False
    scale_cols = st.multiselect("Chọn các biến quan sát của thang đo", num_cols)
    if not scale_cols:
        st.info("Chọn ít nhất 2 biến quan sát.")
        return [], "", False
    if len(scale_cols) < 2:
        st.warning("Cần chọn ít nhất 2 biến.")
        return [], "", False

    res = cronbach.analyze_scale(df, scale_cols)
    c1, c2 = st.columns([1, 3])
    c1.metric("Cronbach's Alpha", f"{res['alpha']:.4f}")
    c2.info(res["verdict"])
    st.dataframe(res["summary"], use_container_width=True)
    st.markdown("**Giải thích:** " + interpretation.interpret_alpha(res["alpha"], res["verdict"], res["drop_items"]))
    for s in interpretation.suggest_improvements_alpha(res["alpha"], res["drop_items"]):
        st.markdown(f"- {s}")

    data_qs = game.questions_cronbach(res["alpha"], res["drop_items"], res["verdict"])
    ctx = (
        f"Cronbach's Alpha = {res['alpha']:.4f}. {res['verdict']}\n"
        f"Biến: {', '.join(scale_cols)}\n"
        f"Đề xuất loại: {res['drop_items'] or 'không có'}\n" + res["summary"].to_string()
    )
    return data_qs, ctx, True


def step_efa(df, summary) -> tuple[list[dict], str, bool]:
    st.subheader("Phân tích nhân tố khám phá (EFA)")
    num_cols = summary["numeric_cols"]
    if not num_cols:
        st.info("Cần có biến định lượng.")
        return [], "", False
    efa_cols = st.multiselect("Chọn các biến quan sát", num_cols)
    if not efa_cols:
        st.info("Chọn ít nhất 2 biến.")
        return [], "", False
    if len(efa_cols) < 2:
        st.warning("Cần chọn ít nhất 2 biến.")
        return [], "", False

    kmo = efa.run_kmo_bartlett(df[efa_cols])
    k1, k2, k3 = st.columns(3)
    k1.metric("KMO", f"{kmo['kmo']:.4f}")
    k2.metric("Bartlett Chi²", f"{kmo['bartlett_chi2']:.2f}")
    k3.metric("Bartlett p-value", f"{kmo['bartlett_p']:.4f}")

    n_factors = st.slider("Số nhân tố", 1, len(efa_cols), value=min(3, len(efa_cols)))
    rotation = st.selectbox(
        "Phương pháp xoay",
        ["varimax", "promax", "oblimin", "None"],
        format_func=lambda x: {"varimax": "Varimax (trực giao)", "promax": "Promax (xiên)", "oblimin": "Oblimin (xiên)", "None": "Không xoay"}[x],
    )
    rot = None if rotation == "None" else rotation

    result = efa.run_efa(df[efa_cols], n_factors, rotation=rot)
    st.subheader("Phương sai giải thích")
    st.dataframe(result["variance_table"], use_container_width=True)
    st.subheader("Ma trận hệ số tải nhân tố")
    st.dataframe(result["loadings"], use_container_width=True)
    st.subheader("Gán biến vào nhân tố")
    st.dataframe(efa.assign_items_to_factors(result["loadings"]), use_container_width=True)
    st.markdown("**Giải thích:** " + interpretation.interpret_efa(kmo, result["variance_table"]))
    for s in interpretation.suggest_improvements_efa(kmo, result["variance_table"]):
        st.markdown(f"- {s}")

    data_qs = game.questions_efa(kmo, result["variance_table"], n_factors)
    ctx = (
        f"KMO = {kmo['kmo']:.4f}, Bartlett p = {kmo['bartlett_p']:.4f}\n"
        f"Số nhân tố = {n_factors}, xoay = {rotation}\n"
        + result["variance_table"].to_string() + "\n" + result["loadings"].to_string()
    )
    return data_qs, ctx, True


def step_correlation(df, summary) -> tuple[list[dict], str, bool]:
    st.subheader("Phân tích tương quan Pearson")
    num_cols = summary["numeric_cols"]
    if not num_cols:
        st.info("Cần có biến định lượng.")
        return [], "", False
    corr_cols = st.multiselect("Chọn các biến", num_cols, default=num_cols[: min(8, len(num_cols))])
    if len(corr_cols) < 2:
        st.info("Chọn ít nhất 2 biến.")
        return [], "", False

    corr_mat = correlation.pearson_correlation(df, corr_cols)
    pval_mat = correlation.pearson_pvalues(df, corr_cols)
    pairs = correlation.significant_pairs(corr_mat, pval_mat)
    st.subheader("Ma trận hệ số tương quan")
    st.dataframe(corr_mat, use_container_width=True)
    st.subheader("Các cặp có ý nghĩa")
    st.dataframe(pairs, use_container_width=True)
    st.markdown("**Giải thích:** " + interpretation.interpret_correlation(pairs))

    data_qs = game.questions_correlation(pairs)
    ctx = "Ma trận tương quan:\n" + corr_mat.to_string()
    return data_qs, ctx, True


def step_regression(df, summary) -> tuple[list[dict], str, bool]:
    st.subheader("Hồi quy tuyến tính")
    num_cols = summary["numeric_cols"]
    if not num_cols:
        st.info("Cần có biến định lượng.")
        return [], "", False
    dep_var = st.selectbox("Biến phụ thuộc (Y)", num_cols)
    indep_vars = st.multiselect("Biến độc lập (X)", [c for c in num_cols if c != dep_var])
    if not indep_vars:
        st.info("Chọn ít nhất một biến độc lập.")
        return [], "", False

    fit = regression.fit_ols(df, dep_var, indep_vars)
    st.subheader("Phương trình hồi quy ước lượng")
    st.code(regression.model_equation(fit), language="text")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("R²", f"{fit['r2']:.4f}")
    c2.metric("Adjusted R²", f"{fit['adj_r2']:.4f}")
    c3.metric("F (ANOVA)", f"{fit['f_stat']:.2f}")
    c4.metric("F p-value", f"{fit['f_pvalue']:.4f}")
    st.subheader("Bảng hệ số hồi quy")
    st.dataframe(fit["coefficients"], use_container_width=True)
    st.subheader("Kiểm tra đa cộng tuyến (VIF)")
    vif_df = fit["vif"].rename("VIF").to_frame()
    vif_df["Đa cộng tuyến (VIF >= 10)"] = vif_df["VIF"] >= 10
    st.dataframe(vif_df, use_container_width=True)
    for line in interpretation.interpret_regression(fit):
        st.markdown(f"- {line}")
    for s in interpretation.suggest_improvements_regression(fit):
        st.markdown(f"- {s}")

    data_qs = game.questions_regression(fit)
    ctx = (
        regression.model_equation(fit)
        + f"\nR² = {fit['r2']:.4f}, Adjusted R² = {fit['adj_r2']:.4f}, F = {fit['f_stat']:.2f}, p = {fit['f_pvalue']:.4f}\n"
        + fit["coefficients"].to_string() + "\nVIF:\n" + fit["vif"].to_string()
    )
    return data_qs, ctx, True


STEP_RENDERERS = {
    "descriptive": step_descriptive,
    "cronbach": step_cronbach,
    "efa": step_efa,
    "correlation": step_correlation,
    "regression": step_regression,
}


# ---------------------------------------------------------------------------
# Trang người trình bày (wizard)
# ---------------------------------------------------------------------------
def _nav_targets(stage: str, step_idx: int) -> tuple:
    """Trả về (trạng thái trước, trạng thái sau) dạng (stage, step_idx) hoặc None."""
    if stage == "upload":
        return ("landing", 0), ("check", 0)
    if stage == "check":
        return ("upload", 0), ("steps", 0)
    if stage == "steps":
        prev_state = ("check", 0) if step_idx == 0 else ("steps", step_idx - 1)
        next_state = ("done", 0) if step_idx == len(STEPS) - 1 else ("steps", step_idx + 1)
        return prev_state, next_state
    if stage == "done":
        return ("steps", len(STEPS) - 1), None
    return None, None


def render_nav_bar(stage: str, step_idx: int) -> None:
    """Thanh điều hướng: Home / Lùi lại / Tiếp tục."""
    if stage == "landing":
        return
    prev_state, next_state = _nav_targets(stage, step_idx)

    def go(s: str, si: int) -> None:
        st.session_state["stage"] = s
        st.session_state["step_idx"] = si
        st.rerun()

    col_home, col_back, col_next, col_spacer = st.columns([1, 1, 1, 5])
    if col_home.button("🏠 Home", key="nav_home", use_container_width=True):
        go("landing", 0)
    if prev_state and col_back.button("⬅️ Lùi lại", key="nav_back", use_container_width=True):
        go(*prev_state)
    if next_state and col_next.button("Tiếp tục ➡️", key="nav_next", use_container_width=True):
        go(*next_state)
    st.markdown("---")


def presenter_view() -> None:
    room_id = get_room_id()
    ai_cfg = ai.get_config()
    stage = st.session_state.get("stage", "landing")
    step_idx = st.session_state.get("step_idx", 0)

    # Đảm bảo đã tải dữ liệu trước khi vào các bước phân tích
    if stage in ("check", "steps", "done") and st.session_state.get("df") is None:
        stage = "upload"
        st.session_state["stage"] = "upload"
        st.session_state["step_idx"] = 0

    with st.sidebar:
        st.markdown("### 🎮 Bảng điều khiển")
        # Bảng xếp hạng người chơi (tự làm mới, điểm cao → thấp)
        st.fragment(sidebar_leaderboard, run_every=5)(room_id)

        # Trạng thái kết nối AI
        ai.render_status(ai_cfg)

        # Slicer chọn phần phân tích
        if stage == "steps":
            st.markdown("---")
            st.markdown("### 🧭 Slicer phân tích")
            choice = st.selectbox(
                "Chuyển đến phần",
                list(range(len(STEPS))),
                format_func=lambda i: f"{STEPS[i][2]}. {STEPS[i][1]}",
                index=step_idx,
            )
            if choice != step_idx:
                st.session_state["step_idx"] = choice
                st.rerun()

        with st.expander("🔗 Cài đặt", expanded=False):
            origin = get_origin()
            pub_url = st.text_input("URL công khai cho người tham gia", value=origin)
            if pub_url and pub_url != origin:
                st.session_state["origin"] = pub_url.rstrip("/")

    # Thanh điều hướng (Home / Lùi / Tiếp)
    render_nav_bar(stage, step_idx)

    if stage == "landing":
        theme.hero()
        st.markdown(theme.card("Hướng dẫn", "Tải lên bộ dữ liệu đã làm sạch, kiểm tra chất lượng, rồi đi qua từng bước phân tích. Ở mỗi bước có trò chơi QR để cả lớp cùng tham gia."), unsafe_allow_html=True)

        # Slide bài nhóm (Canva) - hiển thị trực tiếp
        st.markdown("### 📖 Slide bài nhóm")
        c_btn, c_note = st.columns([1, 3])
        c_btn.link_button(
            "🔲 Phóng to toàn màn hình",
            "https://www.canva.com/design/DAHWBaLveP8/cyOuZSUx3yKO6xa4PTiaUw/view",
            use_container_width=True,
        )
        c_note.caption("Bấm nút để mở slide ở chế độ toàn màn hình, dễ dàng chuyển slide khi thuyết trình.")
        components.iframe(
            "https://www.canva.com/design/DAHWBaLveP8/cyOuZSUx3yKO6xa4PTiaUw/view?embed",
            height=520,
        )

        # Mời tham gia bằng QR
        st.markdown("### 🎮 Mời các bạn tham gia trò chơi")
        if "show_join_qr" not in st.session_state:
            st.session_state["show_join_qr"] = False

        if not st.session_state["show_join_qr"]:
            if st.button("📱 Tạo mã QR cho người tham gia", key="join_qr_btn", use_container_width=True):
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
                    "**Quét mã QR bằng điện thoại** để tham gia trò chơi. "
                    "Nhập tên xong, tên các bạn sẽ hiện ngay ở **bảng xếp hạng** bên trái."
                )
                st.markdown(theme.card("Sẵn sàng chưa?", "Mọi người quét QR và nhập tên trước, khi bạn bắt đầu phân tích và đến từng phần sẽ có câu hỏi mới để trả lời và tính điểm."), unsafe_allow_html=True)

        # Bắt đầu phân tích
        st.markdown("### 📊 Bắt đầu phân tích dữ liệu")
        c = st.columns(3)
        if c[1].button("🚀 Bắt đầu", key="start_btn", use_container_width=True):
            st.session_state["stage"] = "upload"
            st.rerun()
        return

    # Từ đây trở đi cần dữ liệu
    df = st.session_state.get("df")

    if stage == "upload":
        theme.step_badge(1, "Tải lên dữ liệu")
        uploaded = st.file_uploader("Chọn file (.csv hoặc .xlsx)", type=["csv", "xlsx", "xls"])
        if uploaded is not None:
            try:
                raw = dl.read_data(uploaded.getvalue(), uploaded.name)
                st.session_state["df"] = dl.clean_data(raw)
                st.session_state["filename"] = uploaded.name
                df = st.session_state["df"]
            except Exception as e:  # noqa: BLE001
                st.error(f"Lỗi khi đọc file: {e}")

        if df is not None:
            summary = dl.summarize_data(df)
            st.session_state["summary"] = summary
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Số dòng", f"{summary['n_rows']:,}")
            col2.metric("Số cột", summary["n_cols"])
            col3.metric("Cột định lượng", len(summary["numeric_cols"]))
            col4.metric("Cột phân loại", len(summary["categorical_cols"]))
            with st.expander("Xem trước dữ liệu"):
                st.dataframe(df.head(100), use_container_width=True)
            if st.button("🔍 Kiểm tra dữ liệu", key="check_btn", use_container_width=True):
                st.session_state["stage"] = "check"
                st.rerun()
        return

    if stage == "check":
        theme.step_badge(1, "Kiểm tra chất lượng dữ liệu")
        df = st.session_state["df"]
        completeness = dq.check_completeness(df)
        consistency = dq.check_consistency(df)
        issues = dq.summarize_quality(completeness, consistency)
        for issue in issues:
            if issue["mức"] == "error":
                st.error(issue["msg"])
            elif issue["mức"] == "warning":
                st.warning(issue["msg"])
            elif issue["mức"] == "success":
                st.success(issue["msg"])
            else:
                st.info(issue["msg"])

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

        if st.button("➡️ Tiếp tục đến các bước phân tích", key="to_steps_btn", use_container_width=True):
            st.session_state["stage"] = "steps"
            st.session_state["step_idx"] = 0
            st.rerun()
        if st.button("⬅️ Chọn lại file", key="back_upload_btn"):
            st.session_state["stage"] = "upload"
            st.rerun()
        return

    if stage == "steps":
        df = st.session_state["df"]
        summary = st.session_state["summary"]
        step_idx = st.session_state.get("step_idx", 0)
        section_key, step_label, step_no = STEPS[step_idx]

        # Thanh tiến trình
        st.progress((step_idx + 1) / len(STEPS))
        theme.step_badge(step_no, step_label)

        renderer = STEP_RENDERERS[section_key]
        if section_key == "descriptive":
            data_qs, ctx = renderer(df, summary)
            ready = True
        else:
            data_qs, ctx, ready = renderer(df, summary)

        # Trò chơi + QR (sinh câu hỏi một lần cho mỗi phần để giữ ổn định)
        qkey = f"questions_{section_key}"
        if qkey not in st.session_state:
            st.session_state[qkey] = game.build_questions(section_key, data_qs)
        questions = st.session_state[qkey]
        if ready:
            render_live_quiz(section_key, step_label, questions, get_room_id())

        ai.render_ai_enhancements(step_label, ctx, section_key, ai_cfg)

        st.markdown("---")
        st.markdown("### 🧭 Điều hướng 5 phần phân tích")
        cols = st.columns(len(STEPS))
        for i in range(len(STEPS)):
            if cols[i].button(
                str(i + 1),
                key=f"nav_{i}",
                use_container_width=True,
                disabled=(i == step_idx),
                help=STEPS[i][1],
            ):
                st.session_state["step_idx"] = i
                st.rerun()
        st.caption(f"Phần hiện tại: **{step_no}. {step_label}** · Dùng nút Lùi/Tiếp ở trên để qua lại")
        return

    if stage == "done":
        theme.hero()
        st.markdown("## 🎉 Hoàn tất quy trình phân tích")
        st.markdown(theme.card("Tổng kết", "Bạn đã đi qua đầy đủ quy trình: Thống kê mô tả → Cronbach's Alpha → EFA → Tương quan → Hồi quy, kèm trò chơi QR cho cả lớp."), unsafe_allow_html=True)
        scoreboard_fragment(get_room_id())
        if st.button("🔄 Bắt đầu lại", key="restart_btn"):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()
        return


# ---------------------------------------------------------------------------
# Điểm vào
# ---------------------------------------------------------------------------
def main() -> None:
    theme.inject_css()
    qp = st.query_params
    if qp.get("view") == "play":
        audience.render_play_view()
        return
    presenter_view()


if __name__ == "__main__":
    main()
