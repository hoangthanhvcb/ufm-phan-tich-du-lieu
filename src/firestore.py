"""Lưu trữ dữ liệu trò chơi bằng Cloud Firestore.

Vì sao chuyển từ Google Sheets:
    Sheets chỉ cho 60 lần đọc và 60 lần ghi mỗi phút **mỗi tài khoản service
    account**. Lớp 30-40 học sinh cùng poll trạng thái mỗi giây là vượt ngay,
    và lỗi 429 làm hỏng bảng xếp hạng.

    Firestore dùng chung service account nhưng tính theo *số tài liệu* đọc/ghi:
    gói miễn phí 50.000 lượt đọc + 20.000 lượt ghi **mỗi ngày**, và ghi theo lô
    (batch) nên một vòng chơi chỉ tốn vài chục lượt.

Cấu trúc (mỗi collection tương ứng một bảng cũ, mỗi tài liệu là một dòng):
    rooms/{room}                        room_id, current_section
    sections/{room}|{section}           questions (JSON)
    players/{room}|{device}             room_id, device_id, name, joined_at,
                                        total_score, total_questions, sections_done
    answers/{room}|{section}|{device}   name, score, total, answered_at
    responses/{room}|{section}|{device}|{q_index}
                                        picked, correct, points, remaining, answered_at
    quiz_state/{room}|{section}         questions, q_index, deadline, active

Tên tài liệu được tạo từ khoá nên ghi đè đúng dòng cần sửa, không nhân bản điểm.
"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime

from src import gsheets

# Dùng chung exception với gsheets để lớp room.py xử lý thống nhất.
QuotaExceeded = gsheets.QuotaExceeded

COLLECTIONS = (
    "rooms",
    "sections",
    "players",
    "answers",
    "responses",
    "quiz_state",
)

# Số khoá tạo nên document id cho từng collection.
_ID_KEYS = {
    "rooms": 1,
    "sections": 2,
    "players": 2,
    "answers": 3,
    "responses": 4,
    "quiz_state": 2,
}

# Tên trường tương ứng với từng cột của dòng (giống hàng trong Sheets).
FIELDS = {
    "rooms": ["room_id", "current_section"],
    "sections": ["room_id", "section", "questions"],
    "players": ["room_id", "device_id", "name", "joined_at"],
    "answers": ["room_id", "section", "device_id", "name", "score", "total", "answered_at"],
    "responses": [
        "room_id", "section", "device_id", "q_index", "picked",
        "correct", "points", "remaining", "answered_at",
    ],
    "quiz_state": ["room_id", "section", "questions", "q_index", "deadline", "active"],
}

_client_lock = threading.Lock()
_client = None
_probe: bool | None = None


def _project_id() -> str | None:
    for src in (os.environ.get("GOOGLE_PROJECT_ID"),
                os.environ.get("GCP_PROJECT_ID"),
                os.environ.get("GOOGLE_CLOUD_PROJECT")):
        if src:
            return src
    creds = gsheets._load_creds()
    return getattr(creds, "project_id", None)


def _db():
    """Tạo (và cache) client Firestore từ service account đang dùng."""
    global _client
    with _client_lock:
        if _client is not None:
            return _client
        from google.cloud import firestore

        creds = gsheets._load_creds()
        if creds is None:
            return None
        # Firestore cần scope cloud-platform, khác scope spreadsheets.
        creds = creds.with_scopes(["https://www.googleapis.com/auth/cloud-platform"])
        _client = firestore.Client(project=_project_id(), credentials=creds)
        return _client


def is_available() -> bool:
    """Firestore đã bật và dùng được không (có thử đọc thật 1 lần, cache kết quả)."""
    global _probe
    if _probe is not None:
        return _probe
    try:
        db = _db()
        if db is None:
            _probe = False
            return False
        # Đọc thử: nếu API chưa bật hoặc database chưa tạo thì sẽ lỗi.
        db.collection("rooms").limit(1).get()
        _probe = True
    except Exception:
        _probe = False
    return _probe


def _sid(*parts) -> str:
    """Ghép các khoá thành document id (Firestore không cho phép ký tự '/')."""
    return "~".join(str(p) for p in parts)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _doc_id(table: str, row: list[str]) -> str:
    return _sid(*row[: _ID_KEYS[table]])


def _clean(data: dict) -> dict:
    """Firestore không chấp nhận None -> bỏ các trường rỗng."""
    return {k: v for k, v in data.items() if v is not None}


def _to_doc(table: str, row: list[str]) -> dict:
    """Đổi một dòng (danh sách chuỗi) thành dict trường Firestore."""
    names = FIELDS[table]
    out = {}
    for i, name in enumerate(names):
        if i >= len(row):
            break
        val = row[i]
        if val == "":
            continue
        out[name] = val
    return out


# ---------------------------------------------------------------------------
# Ghi
# ---------------------------------------------------------------------------
def api_usage() -> dict:
    """Firestore không áp dụng hạn mức 60/phút kiểu Sheets."""
    return {"read": 0, "write": 0, "limit": 10**9}


def flush_pending() -> None:
    """Firestore ghi theo batch ngay nên không có hàng đợi chờ."""
    return None


def upsert_many(table: str, key_indices: list[int], new_rows: list[list[str]]) -> None:
    """Ghi nhiều dòng trong MỘT lô (Firestore batch, tối đa 500 thao tác/lô).

    Với `answers` còn phải cập nhật tổng điểm tích lũy trên hồ sơ người chơi để
    bảng xếp hạng chỉ cần đọc đúng 1 collection.
    """
    if not new_rows:
        return
    db = _db()
    if db is None:
        raise QuotaExceeded("Firestore chưa sẵn sàng")

    if table == "answers":
        _write_answers_with_totals(db, new_rows)
        return

    coll = db.collection(table)
    for start in range(0, len(new_rows), 400):
        chunk = new_rows[start : start + 400]
        batch = db.batch()
        for row in chunk:
            # merge=True để không xoá mất trường do đường khác ghi vào
            # (ví dụ tổng điểm tích lũy nằm trên hồ sơ người chơi).
            batch.set(coll.document(_doc_id(table, row)), _clean(_to_doc(table, row)), merge=True)
        batch.commit()


def _write_answers_with_totals(db, new_rows: list[list[str]]) -> None:
    """Ghi điểm từng phần và cộng dồn vào tổng của người chơi."""
    rooms = {r[0] for r in new_rows}
    ans_coll = db.collection("answers")
    pl_coll = db.collection("players")

    # Đọc điểm cũ của đúng các phần sắp ghi (để trừ lại khi ghi đè) và tổng hiện tại.
    ans_ids = {_doc_id("answers", r): r for r in new_rows}
    pl_ids = {_sid(r[0], r[2]): r[2] for r in new_rows}
    old_answers = {s.id: (s.to_dict() or {}) for s in db.get_all([ans_coll.document(i) for i in ans_ids])}
    cur = {s.id: (s.to_dict() or {}) for s in db.get_all([pl_coll.document(i) for i in pl_ids])}

    batch = db.batch()
    for row in new_rows:
        room, section, device, name = row[0], row[1], row[2], row[3]
        try:
            score_i, total_i = int(float(row[4] or 0)), int(float(row[5] or 0))
        except (TypeError, ValueError):
            score_i, total_i = 0, 0
        pid = _sid(room, device)
        prev = cur.get(pid, {})
        old = old_answers.get(_sid(room, section, device), {})

        batch.set(
            ans_coll.document(_sid(room, section, device)),
            _clean(
                {
                    "room_id": room,
                    "section": section,
                    "device_id": device,
                    "name": name,
                    "score": score_i,
                    "total": total_i,
                    "answered_at": _now(),
                }
            ),
        )
        # Ghi đè cùng một phần thì chỉ thay số, không cộng thêm lần nữa.
        batch.set(
            pl_coll.document(pid),
            _clean(
                {
                    "room_id": room,
                    "device_id": device,
                    "name": name,
                    "total_score": int(prev.get("total_score") or 0)
                    - int(old.get("score") or 0) + score_i,
                    "total_questions": int(prev.get("total_questions") or 0)
                    - int(old.get("total") or 0) + total_i,
                    "sections_done": int(prev.get("sections_done") or 0)
                    + (0 if old else 1),
                }
            ),
            merge=True,
        )
    batch.commit()


def reset_all() -> None:
    """Xóa toàn bộ dữ liệu trò chơi."""
    db = _db()
    if db is None:
        return
    for table in COLLECTIONS:
        docs = [d.reference for d in db.collection(table).stream()]
        for i in range(0, len(docs), 400):
            batch = db.batch()
            for ref in docs[i : i + 400]:
                batch.delete(ref)
            if docs[i : i + 400]:
                batch.commit()


# ---------------------------------------------------------------------------
# Đọc / ghi từng thao tác
# ---------------------------------------------------------------------------
def set_current_section(room: str, section: str) -> None:
    db = _db()
    db.collection("rooms").document(room).set(
        {"room_id": room, "current_section": section}, merge=True
    )


def get_current_section(room: str) -> str | None:
    snap = _db().collection("rooms").document(room).get()
    return (snap.to_dict() or {}).get("current_section") or None if snap.exists else None


def save_section_questions(room: str, section: str, questions: list[dict]) -> None:
    _db().collection("sections").document(_sid(room, section)).set(
        {"room_id": room, "section": section, "questions": json.dumps(questions, ensure_ascii=False)}
    )


def get_section_questions(room: str, section: str) -> list[dict] | None:
    snap = _db().collection("sections").document(_sid(room, section)).get()
    if not snap.exists:
        return None
    try:
        return json.loads((snap.to_dict() or {}).get("questions") or "[]")
    except (TypeError, json.JSONDecodeError):
        return None


def register_player(room: str, device_id: str, name: str) -> None:
    _db().collection("players").document(_sid(room, device_id)).set(
        {
            "room_id": room,
            "device_id": device_id,
            "name": (name or "").strip() or "Ẩn danh",
            "joined_at": _now(),
        },
        merge=True,
    )


def get_player(room: str, device_id: str) -> str | None:
    snap = _db().collection("players").document(_sid(room, device_id)).get()
    return (snap.to_dict() or {}).get("name") if snap.exists else None


def save_score(
    room: str, section: str, device_id: str, name: str, score: int, total: int
) -> None:
    upsert_many("answers", [0, 1, 2], [[room, section, device_id, name, score, total]])


def get_scores(room: str, device_id: str) -> list[dict]:
    out = []
    for snap in _db().collection("answers").where("room_id", "==", room).stream():
        d = snap.to_dict() or {}
        if d.get("device_id") != device_id:
            continue
        out.append(
            {"section": d.get("section", ""), "score": int(d.get("score") or 0),
             "total": int(d.get("total") or 0)}
        )
    return out


def save_responses(room: str, section: str, device_id: str, rows: list[dict]) -> None:
    if not rows:
        return
    now = _now()
    upsert_many(
        "responses",
        [0, 1, 2, 3],
        [
            [
                room, section, device_id, int(it["q_index"]),
                str(it.get("picked", "")),
                "1" if it.get("correct") else "0",
                int(it.get("points") or 0),
                f'{float(it.get("remaining") or 0):.1f}',
                now,
            ]
            for it in rows
        ],
    )


def get_responses(room: str, device_id: str, section: str | None = None) -> list[dict]:
    out = []
    for snap in _db().collection("responses").where("room_id", "==", room).stream():
        d = snap.to_dict() or {}
        if d.get("device_id") != device_id:
            continue
        if section is not None and d.get("section") != section:
            continue
        out.append(
            {
                "section": d.get("section", ""),
                "q_index": int(d.get("q_index") or 0),
                "picked": str(d.get("picked") or ""),
                "correct": str(d.get("correct")) in ("1", "True", "true"),
                "points": int(d.get("points") or 0),
                "remaining": float(d.get("remaining") or 0),
            }
        )
    out.sort(key=lambda x: (x["section"], x["q_index"]))
    return out


def scoreboard(room: str) -> list[dict]:
    """Bảng xếp hạng: chỉ đọc collection `players` (tổng điểm đã gộp sẵn)."""
    board = []
    for snap in _db().collection("players").where("room_id", "==", room).stream():
        d = snap.to_dict() or {}
        board.append(
            {
                "name": d.get("name") or "Ẩn danh",
                "device_id": d.get("device_id") or "",
                "total_score": int(d.get("total_score") or 0),
                "total_questions": int(d.get("total_questions") or 0),
                "sections_done": int(d.get("sections_done") or 0),
            }
        )
    board.sort(key=lambda r: (-r["total_score"], -r["total_questions"], r["name"]))
    return board


def player_count(room: str) -> int:
    """Đếm người chơi bằng truy vấn tổng hợp (tốn đúng 1 lượt đọc)."""
    return int(
        _db()
        .collection("players")
        .where("room_id", "==", room)
        .count()
        .get()
        .data()
        .get("count", 0)
    )


def set_quiz_state(
    room: str,
    section: str,
    questions: list[dict],
    q_index: int,
    deadline: float,
    active: bool,
) -> None:
    _db().collection("quiz_state").document(_sid(room, section)).set(
        {
            "room_id": room,
            "section": section,
            "questions": json.dumps(questions, ensure_ascii=False),
            "q_index": int(q_index),
            "deadline": float(deadline),
            "active": bool(active),
        }
    )


def get_quiz_state(room: str, section: str) -> dict | None:
    snap = _db().collection("quiz_state").document(_sid(room, section)).get()
    if not snap.exists:
        return None
    d = snap.to_dict() or {}
    try:
        questions = json.loads(d.get("questions") or "[]")
    except (TypeError, json.JSONDecodeError):
        questions = []
    return {
        "questions": questions,
        "q_index": int(d.get("q_index") or 0),
        "deadline": float(d.get("deadline") or 0.0),
        "active": bool(d.get("active")),
    }


def clear_quiz_state(room: str, section: str) -> None:
    _db().collection("quiz_state").document(_sid(room, section)).delete()