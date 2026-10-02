"""Kết nối AI (Google Gemini / OpenRouter) để tự sinh câu hỏi và gợi ý phân tích."""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request

import streamlit as st

DEFAULT_MODEL = "gemini-2.0-flash"

# OpenRouter thường gỡ model free sau một thời gian, nên có danh sách dự phòng.
DEFAULT_OPENROUTER_MODEL = "qwen/qwen3.8-27b:free"
OPENROUTER_FALLBACK_MODELS = [
    "cohere/north-mini-code:free",
    "nvidia/nemotron-3.5-lightning:free",
    "google/gemma-4-31b-it:free",
]

_LAST_MODEL_USED = ""


def last_model_used() -> str:
    """Model thực sự đã sinh ra câu trả lời (có thể là model dự phòng)."""
    return _LAST_MODEL_USED


def _default_api_key() -> str:
    """Lấy Gemini API key từ Streamlit secrets hoặc biến môi trường."""
    try:
        return (st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY") or "").strip()
    except Exception:
        return (os.environ.get("GEMINI_API_KEY") or "").strip()


def _default_openrouter_key() -> str:
    """Lấy OpenRouter API key từ Streamlit secrets hoặc biến môi trường."""
    try:
        return (st.secrets.get("OPENROUTER_API_KEY") or os.environ.get("OPENROUTER_API_KEY") or "").strip()
    except Exception:
        return (os.environ.get("OPENROUTER_API_KEY") or "").strip()


# ---------------------------------------------------------------------------
# Cấu hình AI (đọc ngầm từ secrets/môi trường, không hiển thị UI)
# ---------------------------------------------------------------------------
def get_config() -> dict:
    """Đọc cấu hình AI ngầm từ secrets/môi trường.

    Ưu tiên OpenRouter nếu có key, ngược lại dùng Gemini.
    """
    gemini_key = _default_api_key()
    openrouter_key = _default_openrouter_key()

    if openrouter_key:
        provider = "openrouter"
        api_key = openrouter_key
        model = os.environ.get("OPENROUTER_MODEL") or DEFAULT_OPENROUTER_MODEL
    elif gemini_key:
        provider = "gemini"
        api_key = gemini_key
        model = os.environ.get("GEMINI_MODEL") or DEFAULT_MODEL
    else:
        provider = "gemini"
        api_key = ""
        model = DEFAULT_MODEL

    return {
        "enabled": bool(api_key),
        "provider": provider,
        "api_key": api_key,
        "model": model,
    }


def render_status(cfg: dict) -> None:
    """Hiển thị trạng thái kết nối AI ngắn gọn (chỉ báo đã/chưa kết nối)."""
    if cfg.get("enabled"):
        name = "OpenRouter" if cfg.get("provider") == "openrouter" else "Google Gemini"
        st.success(f"🤖 AI đã kết nối · {name}")
    else:
        st.warning("🤖 AI chưa kết nối")


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


def _openrouter_once(api_key: str, prompt: str, model: str) -> str:
    """Gọi OpenRouter API (tương thích OpenAI) và trả về văn bản trả lời."""
    url = "https://openrouter.ai/api/v1/chat/completions"
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 4096,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        raise RuntimeError("Phản hồi AI không đúng định dạng mong đợi.") from None


def _call_openrouter(api_key: str, prompt: str, model: str) -> str:
    """Gọi OpenRouter; nếu model đã bị gỡ (404) thì tự thử model dự phòng."""
    global _LAST_MODEL_USED
    candidates = [model] + [m for m in OPENROUTER_FALLBACK_MODELS if m != model]
    last_exc: Exception | None = None
    for cand in candidates:
        try:
            text = _openrouter_once(api_key, prompt, cand)
            _LAST_MODEL_USED = cand
            return text
        except urllib.error.HTTPError as exc:
            last_exc = exc
            if exc.code == 404 and cand != candidates[-1]:
                continue  # model này không còn -> thử model kế tiếp
            raise
        except urllib.error.URLError as exc:
            if "404" in str(exc.reason) and cand != candidates[-1]:
                continue
            raise
    raise last_exc if last_exc else RuntimeError("Không gọi được AI.")


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


def analyze_data_quality(context: str, api_key: str, model: str, provider: str = "gemini") -> str:
    """Yêu cầu AI nhận xét ngắn gọn về chất lượng dữ liệu và gợi ý sửa nếu cần."""
    prompt = (
        "Bạn là chuyên gia phân tích dữ liệu định lượng. Dưới đây là kết quả kiểm tra "
        "chất lượng dữ liệu (tính đầy đủ và nhất quán). Hãy:\n"
        "1) Đưa ra NHẬN XÉT ngắn gọn (2-3 câu) về chất lượng dữ liệu.\n"
        "2) Nếu có vấn đề, đưa ra GỢI Ý CỤ THỂ cách sửa từng vấn đề (mỗi ý một dòng, bắt đầu bằng '- ').\n"
        "3) Kết luận ngắn: dữ liệu có phù hợp để phân tích tiếp hay cần làm sạch lại.\n\n"
        f"KẾT QUẢ KIỂM TRA DỮ LIỆU:\n{context}\n\n"
        "Trả lời bằng tiếng Việt, ngắn gọn, rõ ràng."
    )
    return _call_llm(provider, api_key, prompt, model)


def generate_code(step_name: str, context: str, api_key: str, model: str, provider: str = "gemini") -> str:
    """Yêu cầu AI sinh đoạn code Python và R cho bước phân tích hiện tại."""
    prompt = (
        "Bạn là chuyên gia phân tích dữ liệu định lượng và lập trình thống kê.\n"
        f"Hãy viết code tương ứng cho bước phân tích: '{step_name}'.\n\n"
        "YÊU CẦU BẮT BUỘC:\n"
        "1. Trả lời đúng 2 phần theo mẫu sau, không thêm phần khác:\n"
        "## Python\n```python\n<code>\n```\n\n## R\n```r\n<code>\n```\n"
        "2. Code phải CHẠY ĐƯỢC ĐỘC LẬP: tự đọc file dữ liệu, không cần biến ngoài.\n"
        "3. Dùng ĐÚNG tên cột được cung cấp, không tự đặt tên biến giả.\n"
        "4. Python: dùng pandas/numpy/scipy/statsmodels/sklearn/factor_analyzer. "
        "R: dùng psych/corrplot/stats/e1071/factoextra.\n"
        "5. Comment trong code bằng tiếng Việt, ngắn gọn.\n"
        "6. In kết quả bằng print()/cat() để người dùng kiểm tra.\n\n"
        f"THÔNG TIN DỮ LIỆU VÀ KẾT QUẢ BƯỚC '{step_name}':\n{context}"
    )
    return _call_llm(provider, api_key, prompt, model)


# ---------------------------------------------------------------------------
# Khối giao diện AI nhúng vào từng bước
# ---------------------------------------------------------------------------
def generate_code_for_language(
    step_name: str, context: str, lang: str, api_key: str, model: str, provider: str = "gemini"
) -> str:
    """Sinh code cho một ngôn ngữ cụ thể: 'python' hoặc 'r'.

    Trả về (code, huong_dan) với huong_dan là các bước chạy dạng Markdown.
    """
    lang = lang.lower()
    if lang not in ("python", "r"):
        raise ValueError("lang phải là 'python' hoặc 'r'")

    specs = {
        "python": (
            "PYTHON",
            "pandas, numpy, scipy, statsmodels, scikit-learn, factor_analyzer",
            "```python",
        ),
        "r": (
            "R",
            "psych, corrplot, stats, e1071, factoextra, readr, dplyr",
            "```r",
        ),
    }
    name, pkgs, fence = specs[lang]

    prompt = (
        "Bạn là chuyên gia phân tích dữ liệu định lượng và lập trình thống kê.\n"
        f"Hãy viết code {name} tương ứng cho bước phân tích: '{step_name}'.\n\n"
        f"YÊU CẦU BẮT BUỘC:\n"
        f"1. Trả về đúng 2 phần, không thêm phần khác:\n"
        f"## CODE\n{fence}\n<code>\n```\n\n"
        f"## HƯỚNG DẪN\n"
        f"- Các bước chạy từng dòng (đánh số hoặc dùng '- '), ghi rõ cài đặt gói nếu cần.\n"
        f"2. Code PHẢI CHẠY ĐƯỢC ĐỘC LẬP: tự đọc file dữ liệu, không cần biến ngoài.\n"
        f"3. Chỉ dùng thư viện: {pkgs}.\n"
        f"4. Dùng ĐÚNG tên biến/cột được cung cấp, không tự đặt tên biến giả.\n"
        f"5. Comment trong code bằng tiếng Việt, ngắn gọn.\n"
        f"6. In kết quả để người dùng kiểm tra ("
        f"{'print()' if lang == 'python' else 'print() / cat()'}).\n\n"
        f"THÔNG TIN DỮ LIỆU VÀ KẾT QUẢ BƯỚC '{step_name}':\n{context}"
    )
    raw = _call_llm(provider, api_key, prompt, model)
    code, guide = _split_code_and_guide(raw, lang)
    return code, guide


def _split_code_and_guide(raw: str, lang: str) -> tuple[str, str]:
    """Tách phần code và phần hướng dẫn từ câu trả lời của AI."""
    code = _extract_code_block(raw, lang)
    if not code:
        # Không có fenced block -> lấy từ sau tiêu đề CODE
        parts = re.split(r"##\s*(?:CODE|HƯỚNG DẪN|HUONG DAN)", raw, flags=re.IGNORECASE)
        code = parts[1].strip() if len(parts) > 1 else raw.strip()
        code = re.sub(r"^```[a-zA-Z0-9+#-]*\s*\n?|```$", "", code).strip()
    code = re.sub(r"^```[a-zA-Z0-9+#-]*\s*\n", "", code).strip()

    # Phần hướng dẫn: sau tiêu đề HƯỚNG DẪN
    guide = ""
    gm = re.search(r"##\s*(?:HƯỚNG DẪN|HUONG DAN)(.*)$", raw, re.DOTALL | re.IGNORECASE)
    if gm:
        guide = gm.group(1).strip()
        # Bỏ code block nếu lẫn vào hướng dẫn
        guide = re.sub(r"```.*?```", "", guide, flags=re.DOTALL).strip()
    return code, guide


def _extract_code_block(text: str, lang: str) -> str:
    """Lấy code trong fenced block (ưu tiên đúng ngôn ngữ, không có nhãn thì lấy block đầu)."""
    m = re.search(rf"```{re.escape(lang)}\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if not m:
        m = re.search(r"```[a-zA-Z0-9_+#.-]*\s*\n(.*?)```", text, re.DOTALL)
    return m.group(1).strip() if m else ""


def _api_reason(exc: Exception) -> str:
    """Bóc lý do thật từ phản hồi lỗi của API (body thường có JSON)."""
    import urllib.error

    if not isinstance(exc, urllib.error.HTTPError):
        return str(exc)
    try:
        body = exc.read().decode("utf-8", "replace")
    except Exception:
        return getattr(exc, "reason", str(exc))
    try:
        data = json.loads(body)
    except (TypeError, json.JSONDecodeError):
        return body.strip()[:300] or getattr(exc, "reason", str(exc))
    err = data.get("error", data)
    if isinstance(err, dict):
        return str(err.get("message") or err.get("code") or err)[:300]
    return str(err)[:300]


def friendly_error(exc: Exception, cfg: dict | None = None) -> str:
    """Giải thích lỗi gọi AI theo tiếng Việt, kèm cách sửa cụ thể."""
    import urllib.error

    cfg = cfg or {}
    provider = "OpenRouter" if cfg.get("provider") == "openrouter" else "Google Gemini"
    model = cfg.get("model", "")
    reason = _api_reason(exc)
    code = getattr(exc, "code", None)

    if isinstance(exc, urllib.error.HTTPError) and code == 401:
        extra = ""
        if cfg.get("provider") == "openrouter":
            extra = (
                "\n\n• Key OpenRouter phải bắt đầu bằng `sk-or-v1-`."
                "\n• Nếu bạn dùng key Gemini (bắt đầu bằng `AIza`) thì phải đặt vào "
                "`GEMINI_API_KEY`, không đặt vào `OPENROUTER_API_KEY`."
                "\n• Key có thể đã bị thu hồi/hết hạn → tạo key mới tại openrouter.ai/keys."
            )
        else:
            extra = (
                "\n\n• Key Gemini phải bắt đầu bằng `AIza`."
                "\n• Nếu bạn dùng key OpenRouter thì phải đặt vào `OPENROUTER_API_KEY`."
                "\n• Kiểm tra lại key trong Secrets của app trên Streamlit Cloud."
            )
        return (
            f"❌ **{provider} từ chối key (401 Unauthorized)** — key AI không hợp lệ.\n\n"
            f"* Nhà cung cấp: {provider}\n* Model: `{model}`\n"
            f"* Lý do từ máy chủ: {reason}\n{extra}"
        )

    if isinstance(exc, urllib.error.HTTPError) and code == 402:
        return (
            f"❌ **{provider} (402 Payment Required)** — tài khoản đã hết hạn mức "
            f"hoặc hết credit.\n\n* Model: `{model}`\n* Lý do: {reason}"
        )

    if isinstance(exc, urllib.error.HTTPError) and code == 404:
        return (
            f"❌ **Không tìm thấy model `{model}` trên {provider} (404).**\n\n"
            f"* Lý do: {reason}\n\n"
            f"• OpenRouter đã gỡ bỏ model này. App đã thử các model dự phòng "
            f"(`{'`, `'.join(OPENROUTER_FALLBACK_MODELS)}`) nhưng đều không dùng được.\n"
            f"• Có thể bạn chưa bật bật `data_collection` cho key, hoặc key chưa có quyền dùng model.\n"
            f"• Kiểm tra danh sách model còn hoạt động: https://openrouter.ai/models"
        )

    if isinstance(exc, urllib.error.HTTPError) and code == 429:
        return (
            f"⏳ **{provider} bị giới hạn tần suất (429).** Hãy chờ một lúc rồi thử lại.\n\n"
            f"* Lý do: {reason}"
        )

    return f"❌ Lỗi khi gọi AI ({provider} · `{model}`): {reason}"


KEY_PREFIX_NAMES = [
    ("sk-or-v1-", "OpenRouter"),
    ("sk-or-", "OpenRouter"),
    ("AIza", "Google Gemini"),
    ("sk-ant-", "Anthropic"),
    ("sk-proj-", "OpenAI"),
    ("sk-", "OpenAI hoặc dịch vụ khác"),
    ("ghp_", "GitHub"),
    ("gsk_", "Groq"),
    ("hf_", "Hugging Face"),
    ("nvapi-", "NVIDIA"),
    ("xai-", "xAI"),
]


def key_diagnostic(cfg: dict) -> str:
    """Mô tả trạng thái key: độ dài + 6 ký tự đầu để nhận diện, KHÔNG hiện phần key còn lại."""
    key = cfg.get("api_key") or ""
    if not key:
        return "Chưa có API key"
    k = key.strip()
    provider = cfg.get("provider", "gemini")
    expected = "sk-or-v1-" if provider == "openrouter" else "AIza"
    want_name = "OpenRouter" if provider == "openrouter" else "Google Gemini"
    found_name = next((n for p, n in KEY_PREFIX_NAMES if k.startswith(p)), "không nhận dạng")
    head = k[:6] + "…" if len(k) > 6 else k

    notes: list[str] = []
    if not k.startswith(expected):
        notes.append(
            f"⚠️ cần key {want_name} (bắt đầu `{expected}`) nhưng giá trị trong Secrets "
            f"trông giống: {found_name}"
        )
    if provider == "openrouter" and not k.startswith("sk-or-v1-"):
        notes.append("→ hãy copy key ở openrouter.ai/keys và dán lại, đừng dán tên biến")
    if key != k:
        notes.append("⚠️ thừa khoảng trắng đầu/cuối")
    if any(c in key for c in "\n\r"):
        notes.append("⚠️ thừa dòng")
    if '"' in key or "'" in key:
        notes.append("⚠️ thừa dấu nháy bên trong giá trị")

    base = f"{len(k)} ký tự · `{head}` · {found_name}"
    return base if not notes else base + " · " + " ".join(notes)


def test_connection(cfg: dict) -> tuple[bool, str]:
    """Gọi thử API với prompt ngắn để kiểm tra key/model có dùng được không."""
    if not cfg.get("enabled"):
        return False, "Chưa có API key trong Secrets."
    try:
        out = _call_llm(
            cfg.get("provider", "gemini"),
            cfg["api_key"],
            "Chỉ trả lời đúng một chữ: OK",
            cfg.get("model", DEFAULT_MODEL),
        )
        used = _LAST_MODEL_USED or cfg.get("model", "")
        return True, f"Kết nối thành công (model `{used}`). Phản hồi: {out.strip()[:40]}"
    except Exception as e:  # noqa: BLE001
        return False, friendly_error(e, cfg)


def render_ai_code(
    step_name: str,
    context: str,
    key_prefix: str,
    cfg: dict,
) -> None:
    """2 nút: Sinh code Python và Sinh code R, mỗi nút có ô code + hướng dẫn."""
    st.markdown("---")
    st.markdown("### 🤖 Trợ lý AI — sinh code để tự chạy lại")
    if not cfg.get("enabled"):
        st.caption(
            "🔌 Chưa có API key trong Secrets. Bấm **Kiểm tra kết nối AI** ở cột bên trái "
            "để thiết lập; phần này sẽ dùng được ngay."
        )
        return

    st.caption(
        "Sinh code Python và R tương ứng với dữ liệu bạn vừa tải lên, "
        "kèm hướng dẫn từng bước để bạn chạy độc lập."
    )
    if cfg.get("provider") == "openrouter":
        st.caption(f"Nhà cung cấp: OpenRouter · Model: `{cfg.get('model', '')}`")

    col_py, col_r = st.columns(2)
    for col, lang, icon, label in (
        (col_py, "python", "🐍", "Sinh code Python"),
        (col_r, "r", "📊", "Sinh code R"),
    ):
        with col:
            if st.button(
                f"{icon} {label}",
                key=f"{key_prefix}_btn_code_{lang}",
                use_container_width=True,
                type="primary",
            ):
                with st.spinner(f"AI đang sinh code {lang.upper()}..."):
                    try:
                        code, guide = generate_code_for_language(
                            step_name,
                            context,
                            lang,
                            cfg["api_key"],
                            cfg["model"],
                            cfg.get("provider", "gemini"),
                        )
                        st.session_state[f"{key_prefix}_code_{lang}"] = code
                        st.session_state[f"{key_prefix}_guide_{lang}"] = guide
                    except Exception as e:  # noqa: BLE001
                        st.error(friendly_error(e, cfg))

            code = st.session_state.get(f"{key_prefix}_code_{lang}")
            guide = st.session_state.get(f"{key_prefix}_guide_{lang}")
            if code:
                st.code(code, language=lang)
            if guide:
                with st.expander(f"📖 Hướng dẫn từng bước ({lang.upper()})", expanded=True):
                    st.markdown(guide)
