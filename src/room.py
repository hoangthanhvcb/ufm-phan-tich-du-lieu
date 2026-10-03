"""Lớp lưu trữ trò chơi: dùng Google Sheets nếu có, nếu không thì SQLite (dự phòng).

QUAN TRỌNG - hạn mức Google Sheets:
    Tài khoản dùng `client_email` của service account chỉ được 60 lần ĐỌC và
    60 lần GHI mỗi phút. Với 30-40 điện thoại cùng poll trạng thái mỗi giây,
    cách đọc trực tiếp sẽ vượt hạn mức ngay (lỗi 429) và dữ liệu bị hỏng.

    Vì vậy module này dùng cache đọc theo TTL (_read_cached) và ghi gom
    (gom câu trả lời rồi mới ghi 1 lần) để số lần gọi API luôn thấp hơn hạn mức.
"""
from __future__ import annotations

import json
import os
import secrets
import sqlite3
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path

try:  # Firestore là tuỳ chọn: thiếu thư viện hoặc chưa bật API thì dùng Sheets
    from src import firestore
except Exception:  # noqa: BLE001  # pragma: no cover
    firestore = None

from src import gsheets

DB_PATH = Path(
    os.environ.get("UFM_DB_PATH", str(Path(tempfile.gettempdir()) / "ufm_game.db"))
)

_gsheets_broken = False

# TTL cache đọc (giây). Chọn để tổng số lần đọc/phút luôn < 60.
TTL_QUIZ_STATE = float(os.environ.get("UFM_TTL_QUIZ_STATE", "2"))
TTL_SCOREBOARD = float(os.environ.get("UFM_TTL_SCOREBOARD", "10"))
TTL_PLAYERS = float(os.environ.get("UFM_TTL_PLAYERS", "15"))
TTL_RESPONSES = float(os.environ.get("UFM_TTL_RESPONSES", "8"))

# Trạng thái vòng hỏi chỉ sống ~30 giây và mọi máy đều chạy cùng một tiến trình,
# nên giữ thêm trong RAM: vừa nhanh, vừa gần như không tốn lượt đọc Sheets nào
# (đường đọc nóng nhất khi 45 điện thoại cùng theo dõi đồng hồ đếm ngược).
_RAM_TTL = float(os.environ.get("UFM_RAM_TTL_QUIZ_STATE", "4"))
_ram_quiz: dict[tuple, tuple[float, dict]] = {}

_cache: dict[tuple, tuple[float, object]] = {}
_cache_lock = threading.Lock()

# Ghi theo lô: 35 điện thoại ghi gần như cùng lúc sẽ được gom thành 1 lần ghi.
_batch_lock = threading.Lock()
_pending: dict[str, dict[tuple, list[str]]] = {}
_flush_at: dict[str, float] = {}
FLUSH_DELAY = float(os.environ.get("UFM_FLUSH_DELAY", "0.4"))


def flush_now() -> None:
    """Ghi nốt mọi thay đổi đang chờ gom (gọi khi kết thúc vòng chơi)."""
    with _batch_lock:
        due = {s: dict(d) for s, d in _pending.items() if d}
        _pending.clear()
        _flush_at.clear()
    for sheet, batch in due.items():
        _flush_batch(sheet, batch)


def _batched_upsert(sheet: str, key_indices: list[int], rows: list[list[str]]) -> None:
    """Gom nhiều dòng rồi ghi 1 lần, thay vì ghi từng dòng một."""
    if not rows:
        return
    if isinstance(rows[0], (str, int, float)):  # loi: truyen hang phang
        rows = [rows]
    rows = [[str(v) for v in r] for r in rows]
    with _batch_lock:
        bucket = _pending.setdefault(sheet, {})
        for r in rows:
            bucket[tuple(r[i] for i in key_indices)] = r
        now = time.monotonic()
        if now - _flush_at.get(sheet, 0.0) < FLUSH_DELAY:
            return  # người gọi khác sẽ lo phần ghi
        _flush_at[sheet] = now
    time.sleep(FLUSH_DELAY)  # chờ các máy khác kịp gom vào cùng lô
    with _batch_lock:
        batch = _pending.pop(sheet, {})
    _flush_batch(sheet, batch)


def _flush_batch(sheet: str, batch: dict[tuple, list[str]]) -> None:
    global _quota_hit
    if not batch:
        return
    try:
        _store().upsert_many(sheet, _key_idx(sheet), list(batch.values()))
        _count_api("read")
        _count_api("write")
        _quota_hit = False
    except _store().QuotaExceeded:
        # Vượt hạn mức: giữ nguyên dữ liệu trong hàng đợi, thử lại ở lần gọi sau.
        # KHÔNG chuyển sang SQLite vì sẽ chia đôi dữ liệu và sai bảng xếp hạng.
        _quota_hit = True
        with _batch_lock:
            bucket = _pending.setdefault(sheet, {})
            for k, v in batch.items():
                bucket.setdefault(k, v)
    except Exception:
        _mark_broken()


_SHEET_KEYS = {
    "players": [0, 1],
    "answers": [0, 1, 2],
    "responses": [0, 1, 2, 3],
    "rooms": [0],
    "sections": [0, 1],
    "quiz_state": [0, 1],
}


def _key_idx(sheet: str) -> list[int]:
    return _SHEET_KEYS.get(sheet, [0])

# Số lần đọc/ghi Sheets trong 1 phút, để hiển thị cảnh báo cho người dùng.
_api_calls: dict[str, list[float]] = {"read": [], "write": []}
API_LIMIT_PER_MIN = 60

# True khi vừa dính lỗi 429 (vượt hạn mức) -> dữ liệu đang chờ trong hàng đợi.
_quota_hit = False


def quota_warning() -> str:
    if not _quota_hit:
        return ""
    usage = api_usage()
    return (
        "⚠️ Google Sheets đang chậm do vượt hạn mức API "
        f"({usage['read']} lượt đọc / {usage['write']} lượt ghi trong 1 phút). "
        "Điểm đã trả lời vẫn được giữ và sẽ tự lưu ngay khi hết hạn mức."
    )


def api_usage() -> dict:
    """Thống kê mức dùng API Sheets trong 1 phút gần nhất."""
    now = time.monotonic()
    with _cache_lock:
        out = {}
        for k, calls in _api_calls.items():
            calls[:] = [t for t in calls if now - t < 60]
            out[k] = len(calls)
        out["limit"] = API_LIMIT_PER_MIN
        return out


def _count_api(kind: str) -> None:
    now = time.monotonic()
    with _cache_lock:
        calls = _api_calls[kind]
        calls.append(now)
        if len(calls) > 200:
            del calls[:-120]


def _read_cached(kind: str, key: tuple, ttl: float):
    """Đọc có cache TTL. `kind` = tên bảng, `key` = khoá, `ttl` = hạn cache."""
    ck = (kind, key)
    now = time.monotonic()
    with _cache_lock:
        hit = _cache.get(ck)
        if hit is not None and now - hit[0] < ttl:
            return hit[1]
    value = _read_uncached(kind, key)
    with _cache_lock:
        _cache[ck] = (time.monotonic(), value)
    return value


_READERS = {}


def _read_uncached(kind: str, key: tuple):
    """Đọc thật (bỏ qua cache), chọn đúng hàm đọc theo loại dữ liệu."""
    reader = _READERS.get(kind)
    if reader is None:
        raise KeyError(kind)
    return reader(*key)


def invalidate(kind: str | None = None) -> None:
    """Xoá cache đọc (sau khi ghi xong để người khác thấy ngay)."""
    with _cache_lock:
        if kind is None:
            _cache.clear()
        else:
            for k in [k for k in _cache if k[0] == kind]:
                _cache.pop(k, None)


# Chon noi luu tren cloud: Firestore (giai han 50k luot doc/ngay) duoc uu tien,
# neu chua bat duoc thi dung lai Google Sheets. Dat UFM_BACKEND de ep:
#   auto (mac dinh) | firestore | sheets | sqlite
# Chon noi luu tren cloud: Firestore (giai han 50k luot doc/ngay) duoc uu tien,
# neu chua bat duoc thi dung lai Google Sheets. Dat UFM_BACKEND de ep:
#   auto (mac dinh) | firestore | sheets | sqlite
# Doc tu bien moi truong truoc, neu khong co thi doc tu .streamlit/secrets.toml
# (de doi backend tren Streamlit Cloud ma khong can dong lenh).
def _backend_pref() -> str:
    val = (os.environ.get("UFM_BACKEND") or "").strip().lower()
    if val:
        return val
    try:
        import streamlit as _st

        val = str(_st.secrets.get("UFM_BACKEND") or "").strip().lower()
        if val:
            return val
    except Exception:  # noqa: BLE001
        pass
    return "auto"


BACKEND = _backend_pref()
_cloud_broken = False


def _store():
    """Module lưu trữ đang dùng trên cloud."""
    if BACKEND == "sheets":
        return gsheets
    if firestore is not None and (BACKEND == "firestore" or _firestore_ok()):
        return firestore
    return gsheets


def _firestore_ok() -> bool:
    try:
        return bool(firestore.is_available())
    except Exception:  # noqa: BLE001
        return False


def _use_gsheets() -> bool:
    """Còn dùng nơi lưu trên cloud được không (Firestore hoặc Sheets)."""
    global _cloud_broken
    if _cloud_broken or BACKEND == "sqlite" or firestore is None and BACKEND == "firestore":
        return False
    return _store().is_available()


def backend_name() -> str:
    if not _use_gsheets():
        return "SQLite tạm"
    return "Firestore" if _store() is firestore else "Google Sheets"


def _mark_broken() -> None:
    """Đánh dấu Sheets hỏng.

    Cố ý KHÔNG tự chuyển im lặng: nếu đã ghi một phần sang Sheets rồi mới hỏng,
    chuyển sang SQLite sẽ chia đôi dữ liệu và làm sai bảng xếp hạng. Thay vào
    đó app hiển thị cảnh báo để người dùng biết ngay.
    """
    global _cloud_broken
    _cloud_broken = True


def storage_warning() -> str:
    """Cảnh báo ngắn gọn về tình trạng lưu trữ, hoặc chuỗi rỗng nếu bình thường."""
    if not _cloud_broken:
        return ""
    return (
        "⚠️ Google Sheets tạm thời không phản hồi (có thể vượt hạn mức API). "
        "Dữ liệu vòng này đang lưu tạm cục bộ và **có thể mất khi khởi động lại app**. "
        "Bấm nút Reset để chơi lại từ đầu."
    )


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# SQLite (dự phòng)
# ---------------------------------------------------------------------------
def _conn() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


def _init_db() -> None:
    con = _conn()
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS rooms (
            room_id TEXT PRIMARY KEY, current_section TEXT
        );
        CREATE TABLE IF NOT EXISTS sections (
            room_id TEXT, section TEXT, questions TEXT,
            PRIMARY KEY (room_id, section)
        );
        CREATE TABLE IF NOT EXISTS players (
            room_id TEXT, device_id TEXT, name TEXT, joined_at TEXT,
            PRIMARY KEY (room_id, device_id)
        );
        CREATE TABLE IF NOT EXISTS answers (
            room_id TEXT, section TEXT, device_id TEXT, name TEXT,
            score INTEGER, total INTEGER, answered_at TEXT
        );
        CREATE TABLE IF NOT EXISTS quiz_state (
            room_id TEXT, section TEXT, questions TEXT,
            q_index INTEGER, deadline REAL, active INTEGER,
            PRIMARY KEY (room_id, section)
        );
        CREATE TABLE IF NOT EXISTS responses (
            room_id TEXT, section TEXT, device_id TEXT, q_index INTEGER,
            picked TEXT, correct TEXT, points INTEGER, remaining REAL,
            answered_at TEXT,
            PRIMARY KEY (room_id, section, device_id, q_index)
        );
        """
    )
    con.commit()
    con.close()


def new_room() -> str:
    """Tạo mã phòng 6 ký tự (không cần lưu trữ)."""
    return secrets.token_hex(3).upper()


def reset_all() -> None:
    """Xóa toàn bộ dữ liệu trò chơi (người chơi, điểm, câu hỏi, phần hiện tại)."""
    if _use_gsheets():
        try:
            _store().reset_all()
            with _batch_lock:
                _pending.clear()
                _flush_at.clear()
            invalidate()
            with _cache_lock:
                _ram_quiz.clear()
            return
        except Exception:
            _mark_broken()
    _init_db()
    con = _conn()
    con.execute("DELETE FROM rooms")
    con.execute("DELETE FROM players")
    con.execute("DELETE FROM sections")
    con.execute("DELETE FROM answers")
    con.execute("DELETE FROM responses")
    con.execute("DELETE FROM quiz_state")
    con.commit()
    con.close()
    invalidate()
    with _cache_lock:
        _ram_quiz.clear()


def set_current_section(room: str, section: str) -> None:
    if _use_gsheets():
        try:
            _store().upsert_many("rooms", [0], [[room, section]])
            invalidate("rooms")
            return
        except Exception:
            _mark_broken()
    _init_db()
    con = _conn()
    con.execute(
        "INSERT OR REPLACE INTO rooms (room_id, current_section) VALUES (?, ?)",
        (room, section),
    )
    con.commit()
    con.close()
    invalidate("rooms")


def get_current_section(room: str) -> str | None:
    if _use_gsheets():
        try:
            return _store().get_current_section(room)
        except Exception:
            _mark_broken()
    _init_db()
    con = _conn()
    row = con.execute(
        "SELECT current_section FROM rooms WHERE room_id = ?", (room,)
    ).fetchone()
    con.close()
    return row["current_section"] if row else None


def save_section_questions(room: str, section: str, questions: list[dict]) -> None:
    if _use_gsheets():
        try:
            _store().upsert_many(
                "sections", [0, 1],
                [[room, section, json.dumps(questions, ensure_ascii=False)]],
            )
            return
        except Exception:
            _mark_broken()
    _init_db()
    con = _conn()
    con.execute(
        "INSERT OR REPLACE INTO sections (room_id, section, questions) VALUES (?, ?, ?)",
        (room, section, json.dumps(questions, ensure_ascii=False)),
    )
    con.commit()
    con.close()


def get_section_questions(room: str, section: str) -> list[dict] | None:
    if _use_gsheets():
        try:
            return _store().get_section_questions(room, section)
        except Exception:
            _mark_broken()
    _init_db()
    con = _conn()
    row = con.execute(
        "SELECT questions FROM sections WHERE room_id = ? AND section = ?", (room, section)
    ).fetchone()
    con.close()
    if not row:
        return None
    try:
        return json.loads(row["questions"])
    except (TypeError, json.JSONDecodeError):
        return None


def register_player(room: str, device_id: str, name: str) -> None:
    if _use_gsheets():
        try:
            _batched_upsert(
                "players",
                [0, 1],
                [[room, device_id, name.strip() or "Ẩn danh", _now()]],
            )
            invalidate("players")
            return
        except _store().QuotaExceeded:
            global _quota_hit
            _quota_hit = True
            raise
        except Exception:
            _mark_broken()
    _init_db()
    con = _conn()
    con.execute(
        "INSERT OR REPLACE INTO players (room_id, device_id, name, joined_at) VALUES (?, ?, ?, ?)",
        (room, device_id, name.strip() or "Ẩn danh", _now()),
    )
    con.commit()
    con.close()
    invalidate("players")


def get_player(room: str, device_id: str) -> str | None:
    if _use_gsheets():
        try:
            name = _store().get_player(room, device_id)
            _count_api("read")
            return name or None
        except _store().QuotaExceeded:
            global _quota_hit
            _quota_hit = True
            raise
        except Exception:
            _mark_broken()
    _init_db()
    con = _conn()
    row = con.execute(
        "SELECT name FROM players WHERE room_id = ? AND device_id = ?", (room, device_id)
    ).fetchone()
    con.close()
    return row["name"] if row else None


def save_score(room: str, section: str, device_id: str, name: str, score: int, total: int) -> None:
    if _use_gsheets():
        try:
            _batched_upsert(
                "answers",
                [0, 1, 2],
                [[room, section, device_id, name, score, total, _now()]],
            )
            invalidate("answers")
            invalidate("players")
            return
        except Exception:
            _mark_broken()
    _init_db()
    con = _conn()
    con.execute(
        "INSERT OR REPLACE INTO answers (room_id, section, device_id, name, score, total, answered_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (room, section, device_id, name, score, total, _now()),
    )
    con.commit()
    con.close()
    invalidate("answers")
    invalidate("players")


def save_responses(room: str, section: str, device_id: str, rows: list[dict]) -> None:
    """Ghi các câu đã trả lời của một người chơi trong một vòng.

    Khoá (room, section, device, q_index) nên nộp lại cùng câu chỉ ghi đè,
    không nhân bản. Dữ liệu nằm ở server nên người chơi thoát ra quét lại QR
    vẫn xem lại được các câu đã trả lời.
    """
    if not rows:
        return
    if _use_gsheets():
        try:
            now = _now()
            _batched_upsert(
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
            invalidate("responses")
            return
        except Exception:
            _mark_broken()
    _init_db()
    con = _conn()
    now = _now()
    for item in rows:
        con.execute(
            "INSERT OR REPLACE INTO responses "
            "(room_id, section, device_id, q_index, picked, correct, points, remaining, answered_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                room, section, device_id, int(item["q_index"]),
                str(item.get("picked", "")),
                "1" if item.get("correct") else "0",
                int(item.get("points") or 0),
                float(item.get("remaining") or 0.0),
                now,
            ),
        )
    con.commit()
    con.close()
    invalidate("responses")


def get_responses(room: str, device_id: str, section: str | None = None) -> list[dict]:
    """Đọc lại các câu đã trả lời của một người chơi (từ server), có cache TTL."""
    return _read_cached("responses", (room, device_id, section), TTL_RESPONSES)


def _read_responses_uncached(room: str, device_id: str, section: str | None) -> list[dict]:
    if _use_gsheets():
        try:
            rows = _store().get_responses(room, device_id, section)
            _count_api("read")
            return rows
        except _store().QuotaExceeded:
            global _quota_hit
            _quota_hit = True
            raise
        except Exception:
            _mark_broken()
    _init_db()
    con = _conn()
    if section is None:
        rows = con.execute(
            "SELECT section, q_index, picked, correct, points, remaining FROM responses "
            "WHERE room_id = ? AND device_id = ? ORDER BY section, q_index",
            (room, device_id),
        ).fetchall()
    else:
        rows = con.execute(
            "SELECT section, q_index, picked, correct, points, remaining FROM responses "
            "WHERE room_id = ? AND device_id = ? AND section = ? ORDER BY q_index",
            (room, device_id, section),
        ).fetchall()
    con.close()
    return [
        {
            "section": r["section"],
            "q_index": int(r["q_index"]),
            "picked": r["picked"],
            "correct": str(r["correct"]) == "1",
            "points": int(r["points"] or 0),
            "remaining": float(r["remaining"] or 0.0),
        }
        for r in rows
    ]


def section_scores(room: str, device_id: str) -> dict[str, dict]:
    """Điểm đã ghi của một người chơi, tách theo từng phần (đọc từ server)."""
    out: dict[str, dict] = {}
    try:
        board = scoreboard(room)
    except Exception:
        return out
    for r in board:
        if r.get("device_id") != device_id:
            continue
        out["__total__"] = {
            "score": int(r.get("total_score") or 0),
            "questions": int(r.get("total_questions") or 0),
            "sections": int(r.get("sections_done") or 0),
        }
        break
    if _use_gsheets():
        try:
            for r in _store().get_scores(room, device_id):
                out[r["section"]] = {"score": int(r["score"]), "total": int(r["total"])}
            return out
        except _store().QuotaExceeded:
            global _quota_hit
            _quota_hit = True
            return out
        except Exception:
            _mark_broken()
            return out
    _init_db()
    con = _conn()
    rows = con.execute(
        "SELECT section, score, total FROM answers WHERE room_id = ? AND device_id = ?",
        (room, device_id),
    ).fetchall()
    con.close()
    for r in rows:
        out[r["section"]] = {"score": int(r["score"] or 0), "total": int(r["total"] or 0)}
    return out


def scoreboard(room: str) -> list[dict]:
    """Bảng xếp hạng (có cache TTL: web và điện thoại cùng xem, chỉ đọc 1 lần)."""
    return _read_cached("answers", (room,), TTL_SCOREBOARD)


def _read_scoreboard_uncached(room: str) -> list[dict]:
    if _use_gsheets():
        try:
            rows = _store().scoreboard(room)
            _count_api("read")
            return rows
        except _store().QuotaExceeded:
            global _quota_hit
            _quota_hit = True
            raise
        except Exception:
            _mark_broken()
    _init_db()
    con = _conn()
    rows = con.execute(
        """
        SELECT p.device_id, MAX(p.name) AS name,
               COALESCE(SUM(a.score), 0) AS total_score,
               COALESCE(SUM(a.total), 0) AS total_questions,
               COUNT(a.section) AS sections_done
        FROM players p
        LEFT JOIN answers a ON p.room_id = a.room_id AND p.device_id = a.device_id
        WHERE p.room_id = ?
        GROUP BY p.device_id
        ORDER BY total_score DESC, total_questions DESC
        """,
        (room,),
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def player_count(room: str) -> int:
    """Số người đã vào phòng (cache TTL dài vì đếm cũng cần đọc cả sheet players)."""
    return int(_read_cached("players", (room,), TTL_PLAYERS) or 0)


def _read_player_count_uncached(room: str) -> int:
    if _use_gsheets():
        try:
            n = _store().player_count(room)
            _count_api("read")
            return int(n)
        except _store().QuotaExceeded:
            global _quota_hit
            _quota_hit = True
            raise
        except Exception:
            _mark_broken()
    _init_db()
    con = _conn()
    row = con.execute("SELECT COUNT(*) AS c FROM players WHERE room_id = ?", (room,)).fetchone()
    con.close()
    return int(row["c"])


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
    # Ghi RAM ngay: các máy khác đọc sẽ có dữ liệu mà không tốn lượt Sheets.
    _ram_put_quiz(
        room, section,
        {
            "questions": questions,
            "q_index": int(q_index),
            "deadline": float(deadline),
            "active": bool(active),
        },
    )
    if _use_gsheets():
        try:
            _store().set_quiz_state(room, section, questions, q_index, deadline, active)
            invalidate("quiz_state")
            return
        except Exception:
            _mark_broken()
    _init_db()
    con = _conn()
    con.execute(
        "INSERT OR REPLACE INTO quiz_state (room_id, section, questions, q_index, deadline, active) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            room,
            section,
            json.dumps(questions, ensure_ascii=False),
            int(q_index),
            float(deadline),
            1 if active else 0,
        ),
    )
    con.commit()
    con.close()
    invalidate("quiz_state")


def get_quiz_state(room: str, section: str) -> dict | None:
    """Trạng thái đếm ngược dùng chung cho web và điện thoại.

    Đây là đường đọc nóng nhất. Thứ tự ưu tiên: RAM (tiến trình chung) → cache
    TTL → Google Sheets. Với 45 máy cùng poll, phần lớn lượt đọc được trả từ
    RAM nên không tốn quota.
    """
    ck = ("quiz_state", room, section)
    now = time.monotonic()
    with _cache_lock:
        ram = _ram_quiz.get(ck)
        if ram is not None and _ram_valid(ram, now):
            return ram[1]
        hit = _cache.get(ck)
        if hit is not None and now - hit[0] < TTL_QUIZ_STATE:
            return hit[1]
    state = _get_quiz_state_uncached(room, section)
    now = time.monotonic()
    with _cache_lock:
        _cache[ck] = (now, state)
        if state is not None:
            _ram_quiz[ck] = (now, state)
    return state


def _ram_valid(entry: tuple[float, dict], now: float) -> bool:
    """Bản RAM còn dùng được không.

    Khi câu hỏi đang chạy thì RAM là nguồn đúng nhất: mọi máy đều đọc cùng một
    tiến trình và đồng hồ đếm ngược được tính từ `deadline` chung. Chỉ khi câu đã
    hết giờ mới cần hỏi lại Sheets để lấy trạng thái mới do người trình bày ghi.
    """
    stamp, state = entry
    if now - stamp < _RAM_TTL:
        return True
    try:
        return bool(state.get("active")) and time.time() < float(state.get("deadline") or 0.0)
    except (TypeError, ValueError):
        return False


def _ram_put_quiz(room: str, section: str, state: dict | None) -> None:
    ck = ("quiz_state", room, section)
    with _cache_lock:
        if state is None:
            _ram_quiz.pop(ck, None)
        else:
            _ram_quiz[ck] = (time.monotonic(), state)
        _cache.pop(ck, None)


def _get_quiz_state_uncached(room: str, section: str) -> dict | None:
    if _use_gsheets():
        try:
            state = _store().get_quiz_state(room, section)
            _count_api("read")
            return state
        except _store().QuotaExceeded:
            raise
        except Exception:
            _mark_broken()
    _init_db()
    con = _conn()
    row = con.execute(
        "SELECT questions, q_index, deadline, active FROM quiz_state WHERE room_id = ? AND section = ?",
        (room, section),
    ).fetchone()
    con.close()
    if not row:
        return None
    try:
        questions = json.loads(row["questions"])
    except (TypeError, json.JSONDecodeError):
        questions = []
    return {
        "questions": questions,
        "q_index": int(row["q_index"] or 0),
        "deadline": float(row["deadline"] or 0.0),
        "active": bool(row["active"]),
    }


def clear_quiz_state(room: str, section: str) -> None:
    _ram_put_quiz(room, section, None)
    if _use_gsheets():
        try:
            _store().clear_quiz_state(room, section)
            invalidate("quiz_state")
            return
        except Exception:
            _mark_broken()
    _init_db()
    con = _conn()
    con.execute(
        "DELETE FROM quiz_state WHERE room_id = ? AND section = ?", (room, section)
    )
    con.commit()
    con.close()
    invalidate("quiz_state")


# Đăng ký các hàm đọc cho bộ đệm _read_cached (đặt ở cuối để tránh trước vị trí định nghĩa).
_READERS.update(
    {
        "responses": _read_responses_uncached,
        "answers": _read_scoreboard_uncached,
        "players": _read_player_count_uncached,
    }
)
