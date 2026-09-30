"""Kết nối AI (Google Gemini / OpenRouter) để tự sinh câu hỏi và gợi ý phân tích."""
from __future__ import annotations

import json
import os
import re
import urllib.request

import streamlit as st

DEFAULT_MODEL = "gemini-2.0-flash"
DEFAULT_OPENROUTER_MODEL = "meta-llama/llama-3.3-70b-instruct:free"


def _default_api_key() -> str:
    """Lấy Gemini API key từ Streamlit secrets hoặc biến môi trường."""
    try:
        import streamlit as st

        return st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY") or ""
    except Exception:
        return os.environ.get("GEMINI_API_KEY") or ""


def _default_openrouter_key() -> str:
    """Lấy OpenRouter API key từ Streamlit secrets hoặc biến môi trường."""
    try:
        import streamlit as st

        return st.secrets.get("OPENROUTER_API_KEY") or os.environ.get("OPENROUTER_API_KEY") or ""
    except Exception:
        return os.environ.get("OPENROUTER_API_KEY") or ""


# ---------------------------------------------------------------------------
# Cấu hình ở sidebar
# ---------------------------------------------------------------------------
def sidebar_config() -> dict:
    """Hiển thị cấu hình AI (đặt trong container hiện tại, ví dụ sidebar expander).

    Nếu đã có API key trong secrets/môi trường thì tự điền và tự bật sẵn.
    """
    provider = st.selectbox(
        "Nhà cung cấp AI",
        ["gemini", "openrouter"],
        format_func=lambda p: "Google Gemini" if p == "gemini" else "OpenRouter",
    )
    if provider == "gemini":
        default_key = _default_api_key()
        key_label = "Gemini API key"
        default_model = DEFAULT_MODEL
    else:
        default_key = _default_openrouter_key()
        key_label = "OpenRouter API key"
        default_model = DEFAULT_OPENROUTER_MODEL

    enabled = st.checkbox("Bật AI để sinh câu hỏi & gợi ý", value=bool(default_key))
    api_key = st.text_input(key_label, value=default_key, type="password")
    model = st.text_input("Tên model", value=default_model)

    if enabled and not api_key:
        if provider == "gemini":
            st.caption("Lấy key miễn phí tại https://aistudio.google.com/app/apikey")
        else:
            st.caption("Lấy key miễn phí tại https://openrouter.ai/keys")

    return {
        "enabled": enabled and bool(api_key),
        "provider": provider,
        "api_key": api_key or default_key,
        "model": model or default_model,
    }


# ---------------------------------------------------------------------------
# Gọi API
# ---------------------------------------------------------------------------
def _call_gemini(api_key: str, prompt: str, model: str) -> str:
    """Gọi Gemini REST API và trả về nội dung văn bản trả lời."""
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 2048},
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        raise RuntimeError("Phản hồi AI không đúng định dạng mong đợi.") from None


def _call_openrouter(api_key: str, prompt: str, model: str) -> str:
    """Gọi OpenRouter API (tương thích OpenAI) và trả về văn bản trả lời."""
    url = "https://openrouter.ai/api/v1/chat/completions"
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 2048,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        raise RuntimeError("Phản hồi AI không đúng định dạng mong đợi.") from None


def _call_llm(provider: str, api_key: str, prompt: str, model: str) -> str:
    if provider == "openrouter":
        return _call_openrouter(api_key, prompt, model)
    return _call_gemini(api_key, prompt, model)


def _extract_json(text: str):
    """Tách mảng JSON từ phản hồi (có thể bọc trong markdown)."""
    m = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    if m:
        text = m.group(1)
    start, end = text.find("["), text.rfind("]")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]
    return json.loads(text)


# ---------------------------------------------------------------------------
# Sinh câu hỏi
# ---------------------------------------------------------------------------
def _sanitize_questions(raw: list) -> list[dict]:
    """Chuẩn hóa câu hỏi do AI sinh về đúng cấu trúc của trò chơi."""
    out = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        q = item.get("question")
        opts = item.get("options") or item.get("choices")
        ans = item.get("answer")
        expl = item.get("explanation", "")
        if not q or not isinstance(opts, list) or len(opts) < 2:
            continue
        try:
            ans = int(ans)
        except (TypeError, ValueError):
            continue
        if ans < 0 or ans >= len(opts):
            continue
        out.append(
            {
                "question": str(q),
                "options": [str(o) for o in opts],
                "answer": ans,
                "explanation": str(expl),
            }
        )
    return out


def generate_quiz_questions(
    step_name: str, context: str, api_key: str, model: str, provider: str = "gemini"
) -> list[dict]:
    """Yêu cầu AI sinh câu hỏi trắc nghiệm phù hợp với bước phân tích."""
    prompt = (
        "Bạn là trợ lý giảng dạy môn Phương pháp nghiên cứu khoa học. "
        f"Hãy sinh 3 câu hỏi trắc nghiệm (4 lựa chọn) về bước '{step_name}' trong quy trình "
        "phân tích dữ liệu định lượng. Câu hỏi phải dựa trên dữ liệu/kết quả thực tế dưới đây.\n\n"
        f"THÔNG TIN BƯỚC '{step_name}':\n{context}\n\n"
        "Trả lời DUY NHẤT một mảng JSON, không thêm chú thích. Mỗi phần tử có dạng:\n"
        '{"question": "...", "options": ["A", "B", "C", "D"], "answer": <số 0-3>, "explanation": "..."}\n'
        "Câu hỏi viết bằng tiếng Việt, có đúng một đáp án đúng (answer là chỉ số trong options)."
    )
    text = _call_llm(provider, api_key, prompt, model)
    return _sanitize_questions(_extract_json(text))


# ---------------------------------------------------------------------------
# Sinh gợi ý
# ---------------------------------------------------------------------------
def generate_suggestions(
    step_name: str, context: str, api_key: str, model: str, provider: str = "gemini"
) -> list[str]:
    """Yêu cầu AI đưa ra gợi ý giải thích và cải thiện cho bước phân tích."""
    prompt = (
        "Bạn là chuyên gia phân tích dữ liệu định lượng. "
        f"Dựa trên kết quả thực tế của bước '{step_name}' dưới đây, hãy:\n"
        "1) Giải thích ngắn gọn ý nghĩa kết quả.\n"
        "2) Đưa ra 3-5 gợi ý cụ thể để cải thiện mô hình/khảo sát.\n\n"
        f"KẾT QUẢ BƯỚC '{step_name}':\n{context}\n\n"
        "Trả lời bằng tiếng Việt, mỗi gợi ý trên một dòng bắt đầu bằng dấu gạch ngang '- '."
    )
    text = _call_llm(provider, api_key, prompt, model)
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("-") or line.startswith("•") or line.startswith("*"):
            line = line.lstrip("-•* ").strip()
            if line:
                lines.append(line)
    return lines


# ---------------------------------------------------------------------------
# Khối giao diện AI nhúng vào từng bước
# ---------------------------------------------------------------------------
def render_ai_enhancements(step_name: str, context: str, key_prefix: str, cfg: dict) -> None:
    """Hiển thị nút sinh câu hỏi + gợi ý bằng AI cho một bước."""
    if not cfg.get("enabled"):
        return

    st.markdown("---")
    st.markdown("### 🤖 Trợ lý AI")
    col_q, col_s = st.columns(2)

    q_key = f"{key_prefix}_ai_questions"
    s_key = f"{key_prefix}_ai_suggestions"

    with col_q:
        if st.button("✨ Sinh câu hỏi bằng AI", key=f"{key_prefix}_btn_q"):
            with st.spinner("AI đang sinh câu hỏi..."):
                try:
                    qs = generate_quiz_questions(
                        step_name, context, cfg["api_key"], cfg["model"], cfg.get("provider", "gemini")
                    )
                    if qs:
                        st.session_state[q_key] = qs
                        st.success(f"Đã sinh {len(qs)} câu hỏi.")
                    else:
                        st.warning("AI không sinh được câu hỏi hợp lệ.")
                except Exception as e:  # noqa: BLE001
                    st.error(f"Lỗi khi gọi AI: {e}")

        if q_key in st.session_state:
            from src import game

            game.render_quiz(
                f"{step_name} (AI)",
                st.session_state[q_key],
                f"{q_key}_quiz",
            )

    with col_s:
        if st.button("💡 Gợi ý cải thiện bằng AI", key=f"{key_prefix}_btn_s"):
            with st.spinner("AI đang phân tích..."):
                try:
                    sugg = generate_suggestions(
                        step_name, context, cfg["api_key"], cfg["model"], cfg.get("provider", "gemini")
                    )
                    st.session_state[s_key] = sugg
                except Exception as e:  # noqa: BLE001
                    st.error(f"Lỗi khi gọi AI: {e}")

        if s_key in st.session_state:
            sugg = st.session_state[s_key]
            if sugg:
                for s in sugg:
                    st.markdown(f"- {s}")
            else:
                st.info("AI không trả về gợi ý nào.")
