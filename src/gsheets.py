"""Lưu trữ dữ liệu trò chơi bằng Google Sheets (qua service account).

Cấu trúc bảng tính (một spreadsheet, nhiều sheet):
  - rooms:     room_id, current_section
  - players:   room_id, device_id, name, joined_at
  - sections:  room_id, section, questions (JSON)
  - answers:   room_id, section, device_id, name, score, total, answered_at
  - responses: room_id, section, device_id, q_index, picked, correct, points,
               remaining, answered_at  (từng câu, để xem lại được sau khi quét lại QR)
"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# ---------------------------------------------------------------------------
# Bộ đệm trong RAM
#
# Hạn mức Sheets là 60 lượt/phút cho MỖI service account. Nếu mỗi lần ghi đều
# phải "đọc toàn bộ sheet rồi ghi đè" (read-modify-write) thì lớp 45 máy sẽ tốn
# hơn 150 lượt/phút và dính lỗi 429.
#
# Cách xử lý: giữ bản sao sheet trong RAM làm nguồn chính (mọi phiên Streamlit
# đều chạy chung một tiến trình), sửa trên RAM rồi ghi xuống Sheets theo lô.
# Nhờ vậy đọc không tốn lượt API nào, và mỗi lần ghi chỉ cần đúng 1 lượt ghi
# mà không phải đọc trước.
# ---------------------------------------------------------------------------
_rows: dict[str, list[list[str]]] = {}
_dirty: set[str] = set()
_cache_lock = threading.RLock()
_flush_timer: threading.Timer | None = None
FLUSH_DELAY = float(os.environ.get("UFM_SHEETS_FLUSH_DELAY", "1.5"))

# Đếm lượt API THẬT sự phát sinh, để cảnh báo hạn mức không báo nhầm.
_api: dict[str, list[float]] = {"read": [], "write": []}
API_LIMIT_PER_MIN = 60


def _count_api(kind: str) -> None:
    now = time.monotonic()
    with _cache_lock:
        for k in ("read", "write"):
            bucket = _api[k]
            while bucket and now - bucket[0] > 60:
                bucket.pop(0)
    if kind in _api:
        _api[kind].append(now)


def api_usage() -> dict:
    now = time.monotonic()
    with _cache_lock:
        return {
            "read": sum(1 for t in _api["read"] if now - t <= 60),
            "write": sum(1 for t in _api["write"] if now - t <= 60),
            "limit": API_LIMIT_PER_MIN,
        }


def flush_pending() -> None:
    """Ghi những thay đổi còn trong RAM xuống Sheets ngay (1 lượt ghi/sheet).

    Trả về số lượt ghi thất bại (0 là đã ghi hết). Người gọi quyết định có báo
    lỗi hay không: lỗi mạng tạm thời KHÔNG có nghĩa Google Sheets hỏng.
    """
    global _flush_timer
    with _cache_lock:
        if _flush_timer is not None:
            _flush_timer.cancel()
            _flush_timer = None
        pending = sorted(_dirty)
        _dirty.clear()
    failed = 0
    for sheet in pending:
        with _cache_lock:
            rows = [list(r) for r in _rows.get(sheet, [])]
        try:
            _write_all(sheet, rows)
        except Exception:  # noqa: BLE001
            failed += 1
            # Giữ nguyên dữ liệu trong RAM, đánh dấu bẩn để lần sau ghi lại.
            with _cache_lock:
                _dirty.add(sheet)
    if _dirty:
        _schedule_flush()
    return failed


def _schedule_flush() -> None:
    """Gom các thay đổi rồi ghi sau một khoảng ngắn (1 request cho cả lô)."""
    global _flush_timer
    if _flush_timer is not None:
        return
    t = threading.Timer(FLUSH_DELAY, flush_pending)
    t.daemon = True
    _flush_timer = t
    t.start()

# ID bảng tính (điền qua biến môi trường hoặc Streamlit secrets).
DEFAULT_SHEET_ID = os.environ.get(
    "GOOGLE_SHEET_ID",
    "17CxDL1RRJqMNphS4zEel0O161tAcAleiY8McdLviTok",
)

SHEET_HEADERS = {
    "rooms": ["room_id", "current_section"],
    "players": ["room_id", "device_id", "name", "joined_at"],
    "sections": ["room_id", "section", "questions"],
    "answers": ["room_id", "section", "device_id", "name", "score", "total", "answered_at"],
    "quiz_state": ["room_id", "section", "questions", "q_index", "deadline", "active"],
    "responses": [
        "room_id", "section", "device_id", "q_index",
        "picked", "correct", "points", "remaining", "answered_at",
    ],
}

# Đường dẫn file service account (chạy local).
_SA_FILE = Path(__file__).resolve().parent.parent / "service_account.json"
if not _SA_FILE.exists():
    _SA_FILE = Path(__file__).resolve().parent.parent.parent / "service_account.json"


class QuotaExceeded(Exception):
    """Vượt hạn mức API Sheets (HTTP 429).

    Đây là lỗi TẠM THỜI. Không được coi như hỏng vĩnh viễn, nếu không app sẽ
    âm thầm đổi sang SQLite và chia đôi dữ liệu giữa hai nơi.
    """


def _load_creds():
    """Nạp credentials theo thứ tự: Streamlit secrets → env → file local."""
    cached = getattr(_load_creds, "_cache", "unset")
    if cached != "unset":
        return cached
    creds = _load_creds_uncached()
    _load_creds._cache = creds
    return creds


def _load_creds_uncached():
    try:
        import streamlit as st

        raw = st.secrets.get("gcp_service_account")
        if raw:
            info = json.loads(raw) if isinstance(raw, str) else dict(raw)
            from google.oauth2 import service_account

            return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    except Exception:
        pass

    env = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if env:
        from google.oauth2 import service_account

        return service_account.Credentials.from_service_account_info(
            json.loads(env), scopes=SCOPES
        )

    if _SA_FILE.exists():
        from google.oauth2 import service_account

        return service_account.Credentials.from_service_account_file(str(_SA_FILE), scopes=SCOPES)

    return None


def get_sheet_id() -> str:
    try:
        import streamlit as st

        sid = st.secrets.get("GOOGLE_SHEET_ID") or DEFAULT_SHEET_ID
    except Exception:
        sid = DEFAULT_SHEET_ID
    return sid


def is_available() -> bool:
    return bool(_load_creds() and get_sheet_id())


def _service():
    import streamlit as st

    @st.cache_resource
    def _build():
        from googleapiclient.discovery import build

        creds = _load_creds()
        return build("sheets", "v4", credentials=creds, cache_discovery=False)

    return _build()


def _is_transient(msg: str) -> bool:
    """Lỗi mạng tạm thời hay không (đáng thử lại) hay lỗi thật."""
    needles = (
        "SSL", "WRONG_VERSION_NUMBER", "Connection", "Timeout", "timed out",
        "Temporary failure in name resolution", "Name or service not known",
        "Max retries exceeded", "Network is unreachable", "Broken pipe",
        "RemoteDisconnected", "502", "503", "504",
    )
    return any(n in msg for n in needles)


def _execute(request, *, retries: int = 3, kind: str = ""):
    """Gọi API, tự thử lại khi gặp 429 (quota) hoặc lỗi 5xx tạm thời."""
    if kind:
        _count_api(kind)
    delay = 0.6
    for attempt in range(retries + 1):
        try:
            return request.execute()
        except Exception as exc:  # noqa: BLE001
            status = getattr(getattr(exc, "resp", None), "status", None)
            msg = str(exc)
            if status == 429 or "Quota exceeded" in msg or "rateLimit" in msg:
                if attempt < retries:
                    import time

                    time.sleep(delay)
                    delay *= 2
                    continue
                raise QuotaExceeded(msg) from exc
            if status is not None and 500 <= int(status) < 600 and attempt < retries:
                import time

                time.sleep(delay)
                delay *= 2
                continue
            # Lỗi mạng tạm thời (mất mạng, DNS, proxy, SSL reset): cũng nên thử
            # lại vì chỉ vài giây sau là hết, và không phải lỗi vĩnh viễn.
            if _is_transient(msg) and attempt < retries:
                import time

                time.sleep(delay)
                delay *= 2
                continue
            raise


# Cache tiêu đề các sheet đã biết tồn tại, để không gọi spreadsheets().get()
# ở MỌI lần đọc (mỗi lần đọc đều tốn thêm 1 request vào hạn mức 60/phút).
_known_sheets: set[str] = set()


def _ensure_sheet(sheet_name: str) -> None:
    """Tạo sheet nếu chưa có và ghi dòng tiêu đề (chỉ kiểm tra 1 lần/round)."""
    if sheet_name in _known_sheets:
        return
    service = _service()
    sid = get_sheet_id()
    meta = _execute(service.spreadsheets().get(spreadsheetId=sid), kind="read")
    titles = [s["properties"]["title"] for s in meta.get("sheets", [])]
    _known_sheets.update(titles)
    if sheet_name not in titles:
        _execute(
            service.spreadsheets().batchUpdate(
                spreadsheetId=sid,
                body={"requests": [{"addSheet": {"properties": {"title": sheet_name}}}]},
            ),
            kind="write",
        )
        _execute(
            service.spreadsheets().values().update(
                spreadsheetId=sid,
                range=f"{sheet_name}!A1",
                valueInputOption="RAW",
                body={"values": [SHEET_HEADERS[sheet_name]]},
            ),
            kind="write",
        )
    _known_sheets.add(sheet_name)


def _read_rows(sheet_name: str) -> list[list[str]]:
    """Các dòng dữ liệu của sheet, lấy từ RAM (chỉ gọi API lần đầu).

    Nhờ có bộ đệm, đọc ở lớp học không tốn lượt API nào.
    """
    with _cache_lock:
        if sheet_name in _rows:
            return [list(r) for r in _rows[sheet_name]]
    _ensure_sheet(sheet_name)
    service = _service()
    result = _execute(
        service.spreadsheets()
        .values()
        .get(spreadsheetId=get_sheet_id(), range=sheet_name),
        kind="read",
    )
    rows = result.get("values", [])
    data = [list(r) for r in (rows[1:] if rows else [])]
    with _cache_lock:
        _rows[sheet_name] = data
    return [list(r) for r in data]


def _write_all(sheet_name: str, rows: list[list[str]]) -> None:
    """Ghi đè sheet (tiêu đề + dữ liệu) bằng MỘT lần ghi duy nhất.

    Không dùng values().clear() vì nó tốn thêm 1 request ghi, và dữ liệu của
    app chỉ tăng (trừ lúc reset, nơi clear được gọi riêng).
    """
    _ensure_sheet(sheet_name)
    service = _service()
    headers = SHEET_HEADERS[sheet_name]
    body = [headers] + rows
    ncols = max(len(r) for r in body)
    rng = f"{sheet_name}!A1:{chr(ord('A') + ncols - 1)}{len(body)}"
    _execute(
        service.spreadsheets().values().update(
            spreadsheetId=get_sheet_id(),
            range=rng,
            valueInputOption="RAW",
            body={"values": body},
        ),
        kind="write",
    )


def _upsert(sheet_name: str, key_indices: list[int], new_row: list[str]) -> None:
    """Chèn hoặc cập nhật một dòng theo các cột khóa."""
    upsert_many(sheet_name, key_indices, [new_row])


def _mark_dirty(sheet_name: str) -> None:
    """Đánh dấu sheet đã thay đổi trong RAM và hẹn ghi xuống Sheets."""
    with _cache_lock:
        _dirty.add(sheet_name)
    _schedule_flush()


def upsert_many(
    sheet_name: str, key_indices: list[int], new_rows: list[list[str]]
) -> None:
    """Cập nhật NHIỀU dòng, sửa trên RAM rồi ghi cả lô bằng 1 lượt ghi.

    Không đọc lại sheet mỗi lần ghi (đó là nguyên nhân chính vượt hạn mức).
    """
    if not new_rows:
        return
    with _cache_lock:
        if sheet_name not in _rows:
            pass  # nạp ở dưới qua _read_rows để chỉ tốn 1 lượt đọc
    rows = _read_rows(sheet_name)
    index: dict[tuple, int] = {}
    max_key = max(key_indices) if key_indices else -1
    if key_indices:
        for i, r in enumerate(rows):
            if len(r) <= max_key:
                continue
            index[tuple(r[k] for k in key_indices)] = i
    for new_row in new_rows:
        norm = [str(v) for v in new_row]
        k = tuple(norm[i] for i in key_indices) if key_indices else ()
        if k in index:
            rows[index[k]] = norm
        else:
            index[k] = len(rows)
            rows.append(norm)
    with _cache_lock:
        _rows[sheet_name] = [list(r) for r in rows]
    _mark_dirty(sheet_name)


# ---------------------------------------------------------------------------
# API cho room.py
# ---------------------------------------------------------------------------
def reset_all() -> None:
    """Xóa toàn bộ dữ liệu trò chơi (giữ tiêu đề cột)."""
    sheets = ("rooms", "players", "sections", "answers", "quiz_state", "responses")
    with _cache_lock:
        _rows.clear()
        _dirty.clear()
    for sheet in sheets:
        _ensure_sheet(sheet)
        _execute(
            _service()
            .spreadsheets()
            .values()
            .clear(spreadsheetId=get_sheet_id(), range=sheet),
            kind="write",
        )
    _write_all("rooms", [])


def set_current_section(room: str, section: str) -> None:
    _upsert("rooms", [0], [room, section])


def get_current_section(room: str) -> str | None:
    for r in _read_rows("rooms"):
        if len(r) >= 2 and r[0] == room:
            return r[1] or None
    return None


def save_section_questions(room: str, section: str, questions: list[dict]) -> None:
    _upsert("sections", [0, 1], [room, section, json.dumps(questions, ensure_ascii=False)])


def get_section_questions(room: str, section: str) -> list[dict] | None:
    for r in _read_rows("sections"):
        if len(r) >= 3 and r[0] == room and r[1] == section:
            try:
                return json.loads(r[2])
            except (TypeError, json.JSONDecodeError):
                return None
    return None


def register_player(room: str, device_id: str, name: str) -> None:
    from datetime import datetime

    _upsert("players", [0, 1], [room, device_id, name.strip() or "Ẩn danh", datetime.now().isoformat(timespec="seconds")])


def get_player(room: str, device_id: str) -> str | None:
    for r in _read_rows("players"):
        if len(r) >= 3 and r[0] == room and r[1] == device_id:
            return r[2]
    return None


def save_score(room: str, section: str, device_id: str, name: str, score: int, total: int) -> None:
    from datetime import datetime

    _upsert(
        "answers",
        [0, 1, 2],
        [room, section, device_id, name, str(score), str(total), datetime.now().isoformat(timespec="seconds")],
    )


def save_responses(room: str, section: str, device_id: str, rows: list[dict]) -> None:
    """Ghi tất cả câu trả lời của một vòng trong MỘT lần đọc/ghi duy nhất.

    `rows`: [{q_index, picked, correct, points, remaining}, ...]
    Khoá duy nhất: (room_id, section, device_id, q_index) -> nộp lại câu nào cũng
    ghi đè đúng câu đó, không nhân bản điểm.
    """
    if not rows:
        return
    from datetime import datetime

    now = datetime.now().isoformat(timespec="seconds")
    data = _read_rows("responses")
    index = {}
    for i, r in enumerate(data):
        if len(r) >= 4 and r[0] == room and r[1] == section and r[2] == device_id:
            index[str(r[3])] = i
    for item in rows:
        key = str(int(item["q_index"]))
        row = [
            room, section, device_id, key,
            str(item.get("picked", "")),
            "1" if item.get("correct") else "0",
            str(int(item.get("points") or 0)), f'{float(item.get("remaining") or 0):.1f}',
            now,
        ]
        if key in index:
            data[index[key]] = row
        else:
            index[key] = len(data)
            data.append(row)
    with _cache_lock:
        _rows["responses"] = [list(r) for r in data]
    _mark_dirty("responses")


def get_responses(room: str, device_id: str, section: str | None = None) -> list[dict]:
    """Đọc lại các câu đã trả lời của một người chơi (dùng để xem lại sau khi
    thoát ra rồi quét lại QR - dữ liệu nằm trên server, không mất)."""
    out = []
    for r in _read_rows("responses"):
        if len(r) < 7 or r[0] != room or r[2] != device_id:
            continue
        if section is not None and r[1] != section:
            continue
        try:
            out.append(
                {
                    "section": r[1],
                    "q_index": int(r[3]),
                    "picked": r[4],
                    "correct": str(r[5]).strip().lower() in ("1", "true", "yes"),
                    "points": int(float(r[6] or 0)),
                    "remaining": float(r[7] or 0) if len(r) > 7 else 0.0,
                }
            )
        except (ValueError, IndexError):
            continue
    out.sort(key=lambda x: (x["section"], x["q_index"]))
    return out


def get_scores(room: str, device_id: str) -> list[dict]:
    """Điểm đã ghi của một người chơi, tách theo từng phần."""
    out = []
    for r in _read_rows("answers"):
        if len(r) < 6 or r[0] != room or r[2] != device_id:
            continue
        try:
            out.append(
                {
                    "section": r[1],
                    "score": int(float(r[4] or 0)),
                    "total": int(float(r[5] or 0)),
                }
            )
        except ValueError:
            continue
    return out


def scoreboard(room: str) -> list[dict]:
    """Tổng điểm theo thiết bị (device_id), hiển thị tên HIỆN TẠI của người chơi.

    Mỗi thiết bị = 1 người chơi duy nhất, dù có đổi tên vẫn gộp chung điểm.
    """
    # Tên hiện tại theo device_id
    names: dict[str, str] = {}
    for r in _read_rows("players"):
        if len(r) >= 3 and r[0] == room:
            names[r[1]] = r[2]

    # Tổng điểm theo device_id
    agg: dict[str, dict] = {}
    for r in _read_rows("answers"):
        if len(r) < 6 or r[0] != room:
            continue
        device = r[2]
        try:
            sc = int(r[4])
            tot = int(r[5])
        except ValueError:
            sc, tot = 0, 0
        a = agg.setdefault(
            device,
            {"device_id": device, "total_score": 0, "total_questions": 0, "sections_done": 0},
        )
        a["total_score"] += sc
        a["total_questions"] += tot
        a["sections_done"] += 1

    # Thêm thiết bị đã đăng ký nhưng chưa trả lời
    for device in names:
        if device not in agg:
            agg[device] = {
                "device_id": device,
                "total_score": 0,
                "total_questions": 0,
                "sections_done": 0,
            }

    board = [
        {
            "name": names.get(a["device_id"], "Ẩn danh"),
            "device_id": a["device_id"],
            "total_score": a["total_score"],
            "total_questions": a["total_questions"],
            "sections_done": a["sections_done"],
        }
        for a in agg.values()
    ]
    board.sort(key=lambda x: (-x["total_score"], -x["total_questions"]))
    return board


def player_count(room: str) -> int:
    return sum(1 for r in _read_rows("players") if len(r) >= 2 and r[0] == room)


# ---------------------------------------------------------------------------
# Trạng thái trò chơi đếm ngược (dùng chung cho web và điện thoại)
# ---------------------------------------------------------------------------
def set_quiz_state(
    room: str,
    section: str,
    questions: list[dict],
    q_index: int,
    deadline: float,
    active: bool,
) -> None:
    _upsert(
        "quiz_state",
        [0, 1],
        [
            room,
            section,
            json.dumps(questions, ensure_ascii=False),
            str(q_index),
            f"{deadline:.3f}",
            "1" if active else "0",
        ],
    )


def get_quiz_state(room: str, section: str) -> dict | None:
    for r in _read_rows("quiz_state"):
        if len(r) < 6 or r[0] != room or r[1] != section:
            continue
        try:
            questions = json.loads(r[2])
        except (TypeError, json.JSONDecodeError):
            questions = []
        try:
            q_index = int(float(r[3]))
        except (TypeError, ValueError):
            q_index = 0
        try:
            deadline = float(r[4])
        except (TypeError, ValueError):
            deadline = 0.0
        return {
            "questions": questions,
            "q_index": q_index,
            "deadline": deadline,
            "active": r[5] == "1",
        }
    return None


def clear_quiz_state(room: str, section: str) -> None:
    rows = [
        r
        for r in _read_rows("quiz_state")
        if not (len(r) >= 2 and r[0] == room and r[1] == section)
    ]
    _write_all("quiz_state", rows)
