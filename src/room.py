"""Lớp lưu trữ trò chơi: dùng Google Sheets nếu có, nếu không thì SQLite (dự phòng).

Nếu Google Sheets gặp lỗi (mạng, quyền, key sai) thì tự động chuyển sang SQLite
để app không bị sập.
"""
from __future__ import annotations

import json
import os
import secrets
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

from src import gsheets

DB_PATH = Path(
    os.environ.get("UFM_DB_PATH", str(Path(tempfile.gettempdir()) / "ufm_game.db"))
)

_gsheets_broken = False


def _use_gsheets() -> bool:
    global _gsheets_broken
    if _gsheets_broken:
        return False
    return gsheets.is_available()


def _mark_broken() -> None:
    global _gsheets_broken
    _gsheets_broken = True


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
            gsheets.reset_all()
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


def set_current_section(room: str, section: str) -> None:
    if _use_gsheets():
        try:
            gsheets.set_current_section(room, section)
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


def get_current_section(room: str) -> str | None:
    if _use_gsheets():
        try:
            return gsheets.get_current_section(room)
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
            gsheets.save_section_questions(room, section, questions)
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
            return gsheets.get_section_questions(room, section)
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
            gsheets.register_player(room, device_id, name)
            return
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


def get_player(room: str, device_id: str) -> str | None:
    if _use_gsheets():
        try:
            return gsheets.get_player(room, device_id)
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
            gsheets.save_score(room, section, device_id, name, score, total)
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
            gsheets.save_responses(room, section, device_id, rows)
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


def get_responses(room: str, device_id: str, section: str | None = None) -> list[dict]:
    """Đọc lại các câu đã trả lời của một người chơi (từ server)."""
    if _use_gsheets():
        try:
            return gsheets.get_responses(room, device_id, section)
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
            for row in gsheets._read_rows("answers"):
                if len(row) < 6 or row[0] != room or row[2] != device_id:
                    continue
                try:
                    out[row[1]] = {"score": int(float(row[4] or 0)), "total": int(float(row[5] or 0))}
                except ValueError:
                    continue
            return out
        except Exception:
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
    if _use_gsheets():
        try:
            return gsheets.scoreboard(room)
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
    if _use_gsheets():
        try:
            return gsheets.player_count(room)
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
    if _use_gsheets():
        try:
            gsheets.set_quiz_state(room, section, questions, q_index, deadline, active)
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


def get_quiz_state(room: str, section: str) -> dict | None:
    if _use_gsheets():
        try:
            return gsheets.get_quiz_state(room, section)
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
    if _use_gsheets():
        try:
            gsheets.clear_quiz_state(room, section)
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
