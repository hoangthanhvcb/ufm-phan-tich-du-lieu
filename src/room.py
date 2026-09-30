"""Backend lưu trữ chia sẻ (SQLite) cho trò chơi QR nhiều thiết bị.

Mô hình:
  - room: mã phòng (một buổi trình bày).
  - section: mỗi bước phân tích lưu câu hỏi dạng JSON.
  - players: người chơi theo device_id (nhận diện cùng thiết bị khi quét lại QR).
  - answers: điểm từng phần để tính tổng.
"""
from __future__ import annotations

import json
import os
import secrets
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

DB_PATH = Path(
    os.environ.get("UFM_DB_PATH", str(Path(tempfile.gettempdir()) / "ufm_game.db"))
)


def _conn() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


def init_db() -> None:
    con = _conn()
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS rooms (
            room_id TEXT PRIMARY KEY,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS sections (
            room_id TEXT,
            section TEXT,
            questions TEXT,
            PRIMARY KEY (room_id, section)
        );
        CREATE TABLE IF NOT EXISTS players (
            room_id TEXT,
            device_id TEXT,
            name TEXT,
            joined_at TEXT,
            PRIMARY KEY (room_id, device_id)
        );
        CREATE TABLE IF NOT EXISTS answers (
            room_id TEXT,
            section TEXT,
            device_id TEXT,
            name TEXT,
            score INTEGER,
            total INTEGER,
            answered_at TEXT
        );
        """
    )
    con.commit()
    con.close()


def new_room() -> str:
    """Tạo mã phòng 6 ký tự (chữ hoa + số)."""
    init_db()
    room = secrets.token_hex(3).upper()
    con = _conn()
    con.execute("INSERT OR IGNORE INTO rooms (room_id, created_at) VALUES (?, ?)", (room, _now()))
    con.commit()
    con.close()
    return room


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Câu hỏi của từng phần
# ---------------------------------------------------------------------------
def save_section_questions(room: str, section: str, questions: list[dict]) -> None:
    init_db()
    con = _conn()
    con.execute(
        "INSERT OR REPLACE INTO sections (room_id, section, questions) VALUES (?, ?, ?)",
        (room, section, json.dumps(questions, ensure_ascii=False)),
    )
    con.commit()
    con.close()


def get_section_questions(room: str, section: str) -> list[dict] | None:
    init_db()
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


# ---------------------------------------------------------------------------
# Người chơi
# ---------------------------------------------------------------------------
def register_player(room: str, device_id: str, name: str) -> None:
    init_db()
    con = _conn()
    con.execute(
        "INSERT OR REPLACE INTO players (room_id, device_id, name, joined_at) VALUES (?, ?, ?, ?)",
        (room, device_id, name.strip() or "Ẩn danh", _now()),
    )
    con.commit()
    con.close()


def get_player(room: str, device_id: str) -> str | None:
    init_db()
    con = _conn()
    row = con.execute(
        "SELECT name FROM players WHERE room_id = ? AND device_id = ?", (room, device_id)
    ).fetchone()
    con.close()
    return row["name"] if row else None


# ---------------------------------------------------------------------------
# Điểm số
# ---------------------------------------------------------------------------
def save_score(room: str, section: str, device_id: str, name: str, score: int, total: int) -> None:
    init_db()
    con = _conn()
    con.execute(
        "INSERT OR REPLACE INTO answers (room_id, section, device_id, name, score, total, answered_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (room, section, device_id, name, score, total, _now()),
    )
    con.commit()
    con.close()


def scoreboard(room: str) -> list[dict]:
    """Bảng điểm tổng của tất cả người chơi trong phòng (giảm dần)."""
    init_db()
    con = _conn()
    rows = con.execute(
        """
        SELECT p.name, COALESCE(SUM(a.score), 0) AS total_score,
               COALESCE(SUM(a.total), 0) AS total_questions,
               COUNT(a.section) AS sections_done
        FROM players p
        LEFT JOIN answers a ON p.room_id = a.room_id AND p.device_id = a.device_id
        WHERE p.room_id = ?
        GROUP BY p.name
        ORDER BY total_score DESC, total_questions DESC
        """,
        (room,),
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def scoreboard_by_device(room: str) -> list[dict]:
    """Bảng điểm chi tiết theo từng thiết bị (kèm điểm từng phần)."""
    init_db()
    con = _conn()
    rows = con.execute(
        """
        SELECT p.device_id, p.name,
               COALESCE(SUM(a.score), 0) AS total_score,
               GROUP_CONCAT(a.section || ':' || a.score || '/' || a.total, '; ') AS detail
        FROM players p
        LEFT JOIN answers a ON p.room_id = a.room_id AND p.device_id = a.device_id
        WHERE p.room_id = ?
        GROUP BY p.device_id, p.name
        ORDER BY total_score DESC
        """,
        (room,),
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def player_count(room: str) -> int:
    init_db()
    con = _conn()
    row = con.execute("SELECT COUNT(*) AS c FROM players WHERE room_id = ?", (room,)).fetchone()
    con.close()
    return int(row["c"])
