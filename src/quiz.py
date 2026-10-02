"""Trò chơi câu hỏi đếm ngược, dùng chung cho màn hình web và điện thoại.

Trạng thái (câu hỏi, câu hiện tại, mốc hết giờ) được lưu trong `room`/Google Sheets
nên mọi thiết bị đều thấy CÙNG một câu hỏi và cùng đồng hồ đếm ngược.
"""
from __future__ import annotations

import time

from src import room

PER_QUESTION_SECONDS = 10
MAX_QUESTIONS = 3

# Điểm của một câu: đúng = POINTS_CORRECT + thưởng tốc độ theo thời gian còn lại.
# Sai = 0 điểm. Nhờ vậy xếp hạng vừa phản ánh độ đúng vừa phản ánh tốc độ nộp bài.
POINTS_CORRECT = 10
SPEED_BONUS_MAX = 5


def points_for(remaining: float) -> int:
    """Tổng điểm cho một câu trả lời ĐÚNG, tính cả thưởng tốc độ.

    remaining = số giây còn lại ở thời điểm bấm nộp (do server đo).
    Nộp ngay khi câu mở ra: còn đủ 10s -> 10 + 5 = 15 điểm.
    Nộp ở giây cuối: còn ~0s -> 10 + 0 = 10 điểm.
    """
    ratio = remaining / PER_QUESTION_SECONDS if PER_QUESTION_SECONDS else 0.0
    ratio = max(0.0, min(1.0, ratio))
    return POINTS_CORRECT + int(round(SPEED_BONUS_MAX * ratio))


def max_points_per_question() -> int:
    return POINTS_CORRECT + SPEED_BONUS_MAX

IDLE = {
    "status": "idle",  # idle | running | done
    "active": False,
    "questions": [],
    "q_index": 0,
    "question": None,
    "remaining": PER_QUESTION_SECONDS,
    "total": MAX_QUESTIONS,
    "answered": 0,
}


def start(
    room_id: str,
    section: str,
    questions: list[dict],
    per_question: int = PER_QUESTION_SECONDS,
    max_questions: int = MAX_QUESTIONS,
) -> None:
    """Bắt đầu ván chơi: tối đa `max_questions` câu, mỗi câu `per_question` giây."""
    qs = [q for q in (questions or []) if q.get("question")][:max_questions]
    if not qs:
        return
    room.set_current_section(room_id, section)
    room.save_section_questions(room_id, section, qs)
    room.set_quiz_state(
        room_id,
        section,
        qs,
        0,
        time.time() + per_question,
        True,
    )


def stop(room_id: str, section: str) -> None:
    room.clear_quiz_state(room_id, section)


def is_running(room_id: str, section: str) -> bool:
    state = room.get_quiz_state(room_id, section)
    return bool(state and state.get("active"))


def view(
    room_id: str,
    section: str,
    per_question: int = PER_QUESTION_SECONDS,
) -> dict:
    """Trả về trạng thái hiện tại; tự chuyển câu khi hết giờ."""
    try:
        state = room.get_quiz_state(room_id, section)
    except Exception:
        return dict(IDLE)

    if not state:
        return dict(IDLE)

    questions = state.get("questions") or []
    idx = int(state.get("q_index") or 0)
    deadline = float(state.get("deadline") or 0.0)
    active = bool(state.get("active"))
    now = time.time()

    # Hết giờ -> chuyển sang câu tiếp theo (hoặc kết thúc ván chơi)
    if active and now >= deadline:
        idx += 1
        if idx >= len(questions):
            active = False
            deadline = now
        else:
            deadline = now + per_question
        try:
            room.set_quiz_state(room_id, section, questions, idx, deadline, active)
        except Exception:
            pass

    if not active:
        status = "done" if questions else "idle"
        return {
            "status": status,
            "active": False,
            "questions": questions,
            "q_index": min(idx, len(questions)),
            "question": None,
            "remaining": 0.0,
            "total": len(questions) or MAX_QUESTIONS,
            "answered": len(questions),
        }

    return {
        "status": "running",
        "active": True,
        "questions": questions,
        "q_index": idx,
        "question": questions[idx],
        "remaining": max(0.0, deadline - now),
        "total": len(questions),
        "answered": idx,
    }