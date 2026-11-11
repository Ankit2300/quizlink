"""Plain business logic shared by the MCP tools and the web pages. No AI here."""
import os
from collections import Counter

from db import Attempt, Question, Quiz, Teacher

# Render sets RENDER_EXTERNAL_URL to the service's real public address automatically.
BASE_URL = (os.environ.get("RENDER_EXTERNAL_URL") or os.environ.get("BASE_URL")
            or "http://localhost:8000").rstrip("/")


class QuizError(ValueError):
    pass


def validate_questions(questions: list[dict]) -> list[dict]:
    if not questions:
        raise QuizError("A quiz needs at least one question.")
    clean = []
    for i, q in enumerate(questions, 1):
        text = str(q.get("text", "")).strip()
        options = [str(o).strip() for o in q.get("options", []) if str(o).strip()]
        ci = q.get("correct_index")
        if not text:
            raise QuizError(f"Question {i} has no text.")
        if not 2 <= len(options) <= 6:
            raise QuizError(f"Question {i} needs 2-6 options.")
        if not isinstance(ci, int) or not 0 <= ci < len(options):
            raise QuizError(f"Question {i}: correct_index must be 0..{len(options) - 1}.")
        clean.append({"text": text, "options": options, "correct_index": ci,
                      "explanation": str(q.get("explanation", "") or "").strip(),
                      "topic": str(q.get("topic", "") or "").strip()[:120]})
    return clean


def links(quiz: Quiz) -> dict:
    return {
        "student_url": f"{BASE_URL}/q/{quiz.share_code}",
        "edit_url": f"{BASE_URL}/teacher/quiz/{quiz.id}",
        "results_url": f"{BASE_URL}/teacher/quiz/{quiz.id}/results",
    }


def create_quiz(s, teacher: Teacher, title: str, questions: list[dict],
                time_limit_min: int = 15, description: str = "") -> Quiz:
    title = (title or "").strip()
    if not title:
        raise QuizError("Title is required.")
    quiz = Quiz(teacher=teacher, title=title[:200], description=description or "",
                time_limit_min=max(1, min(int(time_limit_min or 15), 180)))
    for pos, q in enumerate(validate_questions(questions)):
        quiz.questions.append(Question(position=pos, **q))
    s.add(quiz)
    s.commit()
    return quiz


def replace_questions(s, quiz: Quiz, questions: list[dict]):
    """Update questions in place by position so existing student attempts stay linked."""
    clean = validate_questions(questions)
    existing = list(quiz.questions)
    for pos, q in enumerate(clean):
        if pos < len(existing):
            row = existing[pos]
            row.position = pos
            for k, v in q.items():
                setattr(row, k, v)
        else:
            quiz.questions.append(Question(position=pos, **q))
    for row in existing[len(clean):]:
        quiz.questions.remove(row)


def grade(quiz: Quiz, answers: dict) -> tuple[int, int]:
    """answers: {question_id(str|int): chosen_index}. Plain comparison, no AI."""
    score = 0
    for q in quiz.questions:
        chosen = answers.get(str(q.id), answers.get(q.id))
        if chosen is not None and int(chosen) == q.correct_index:
            score += 1
    return score, len(quiz.questions)


def results_summary(quiz: Quiz) -> dict:
    attempts = quiz.attempts
    n = len(attempts)
    wrong = Counter()
    for a in attempts:
        for q in quiz.questions:
            chosen = a.answers.get(str(q.id))
            if chosen is None or int(chosen) != q.correct_index:
                wrong[q.id] += 1
    per_question = [{
        "number": i + 1, "question": q.text, "topic": q.topic,
        "correct_answer": q.options[q.correct_index],
        "students_wrong": wrong[q.id],
        "percent_correct": round(100 * (n - wrong[q.id]) / n) if n else None,
    } for i, q in enumerate(quiz.questions)]
    return {
        "quiz_id": quiz.id, "title": quiz.title, "attempts": n,
        "average_percent": round(100 * sum(a.score / a.total for a in attempts) / n) if n else None,
        "students": [{"name": a.student_name, "score": a.score, "total": a.total,
                      "submitted_at": a.submitted_at.isoformat()} for a in attempts],
        "per_question": per_question,
    }
