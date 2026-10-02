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
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

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


def _load_creds():
    """Nạp credentials theo thứ tự: Streamlit secrets → env → file local."""
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


def _ensure_sheet(sheet_name: str) -> None:
    """Tạo sheet nếu chưa có và ghi dòng tiêu đề."""
    service = _service()
    sid = get_sheet_id()
    meta = service.spreadsheets().get(spreadsheetId=sid).execute()
    titles = [s["properties"]["title"] for s in meta.get("sheets", [])]
    if sheet_name not in titles:
        service.spreadsheets().batchUpdate(
            spreadsheetId=sid,
            body={"requests": [{"addSheet": {"properties": {"title": sheet_name}}}]},
        ).execute()
        service.spreadsheets().values().update(
            spreadsheetId=sid,
            range=f"{sheet_name}!A1",
            valueInputOption="RAW",
            body={"values": [SHEET_HEADERS[sheet_name]]},
        ).execute()


def _read_rows(sheet_name: str) -> list[list[str]]:
    """Đọc các dòng dữ liệu (bỏ dòng tiêu đề)."""
    _ensure_sheet(sheet_name)
    service = _service()
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=get_sheet_id(), range=sheet_name)
        .execute()
    )
    rows = result.get("values", [])
    return rows[1:] if rows else []


def _write_all(sheet_name: str, rows: list[list[str]]) -> None:
    """Ghi đè toàn bộ sheet (tiêu đề + dữ liệu)."""
    _ensure_sheet(sheet_name)
    service = _service()
    headers = SHEET_HEADERS[sheet_name]
    body = [headers] + rows
    service.spreadsheets().values().clear(
        spreadsheetId=get_sheet_id(), range=sheet_name
    ).execute()
    service.spreadsheets().values().update(
        spreadsheetId=get_sheet_id(),
        range=f"{sheet_name}!A1",
        valueInputOption="RAW",
        body={"values": body},
    ).execute()


def _upsert(sheet_name: str, key_indices: list[int], new_row: list[str]) -> None:
    """Chèn hoặc cập nhật một dòng theo các cột khóa."""
    rows = _read_rows(sheet_name)
    target = None
    for i, r in enumerate(rows):
        if len(r) <= max(key_indices):
            continue
        if all(r[k] == str(new_row[k]) for k in key_indices):
            target = i
            break
    norm = [str(v) for v in new_row]
    if target is not None:
        rows[target] = norm
    else:
        rows.append(norm)
    _write_all(sheet_name, rows)


# ---------------------------------------------------------------------------
# API cho room.py
# ---------------------------------------------------------------------------
def reset_all() -> None:
    """Xóa toàn bộ dữ liệu trò chơi (giữ tiêu đề cột)."""
    for sheet in ("rooms", "players", "sections", "answers", "quiz_state", "responses"):
        _write_all(sheet, [])


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
            str(item.get("picked", "")), str(item.get("correct", "")),
            str(int(item.get("points") or 0)), f'{float(item.get("remaining") or 0):.1f}',
            now,
        ]
        if key in index:
            data[index[key]] = row
        else:
            index[key] = len(data)
            data.append(row)
    _write_all("responses", data)


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
                    "correct": r[5] == "1",
                    "points": int(float(r[6] or 0)),
                    "remaining": float(r[7] or 0) if len(r) > 7 else 0.0,
                }
            )
        except (ValueError, IndexError):
            continue
    out.sort(key=lambda x: (x["section"], x["q_index"]))
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
