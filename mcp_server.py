"""MCP tools Claude can call. Claude writes the questions; these tools only save/read data. No AI here."""
from typing import Annotated

from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_request
from pydantic import BaseModel, Field

import logic
from db import Quiz, SessionLocal, Teacher

mcp = FastMCP(
    "QuizLink",
    instructions=(
        "QuizLink hosts quizzes for teachers. When a teacher asks for a quiz/test (from a topic, "
        "notes or a chapter photo), YOU write the multiple-choice questions, then call create_quiz. "
        "Always show the teacher the student_url (to share with students) and edit_url. "
        "To analyse how a class did, call get_quiz_results and explain weak topics yourself."
    ),
)


class QuestionIn(BaseModel):
    text: Annotated[str, Field(description="The question text")]
    options: Annotated[list[str], Field(description="2-6 answer options, usually 4")]
    correct_index: Annotated[int, Field(description="0-based index of the correct option")]
    explanation: Annotated[str, Field(description="Short explanation shown to students after submitting")] = ""
    topic: Annotated[str, Field(description="Sub-topic this question tests, e.g. 'Adding fractions'")] = ""


def _teacher(s) -> Teacher:
    """Workspace is chosen by ?key=... on the MCP URL. Falls back to the demo workspace."""
    key = "demo"
    try:
        key = get_http_request().query_params.get("key") or "demo"
    except Exception:
        pass
    t = s.query(Teacher).filter_by(mcp_key=key).first()
    if not t:
        raise ValueError("Unknown QuizLink key. Check the connector URL.")
    return t


def _own_quiz(s, teacher: Teacher, quiz_id: int) -> Quiz:
    q = s.get(Quiz, quiz_id)
    if not q or q.teacher_id != teacher.id:
        raise ValueError(f"Quiz {quiz_id} not found.")
    return q


@mcp.tool
def create_quiz(
    title: Annotated[str, Field(description="Quiz title, e.g. 'Class 6 - Fractions'")],
    questions: Annotated[list[QuestionIn], Field(description="The questions you wrote")],
    time_limit_min: Annotated[int, Field(description="Time limit in minutes")] = 15,
    description: Annotated[str, Field(description="Optional instructions for students")] = "",
) -> dict:
    """Save a multiple-choice quiz in QuizLink and get a shareable student link.
    Returns quiz_id, student_url (share with students), edit_url and results_url (for the teacher)."""
    with SessionLocal() as s:
        quiz = logic.create_quiz(s, _teacher(s), title, [q.model_dump() for q in questions],
                                 time_limit_min, description)
        return {"quiz_id": quiz.id, "title": quiz.title, "questions": len(quiz.questions),
                "time_limit_min": quiz.time_limit_min, **logic.links(quiz)}


@mcp.tool
def list_quizzes() -> list[dict]:
    """List this teacher's quizzes with number of attempts and links."""
    with SessionLocal() as s:
        t = _teacher(s)
        quizzes = s.query(Quiz).filter_by(teacher_id=t.id).order_by(Quiz.created_at.desc()).all()
        return [{"quiz_id": q.id, "title": q.title, "status": q.status, "questions": len(q.questions),
                 "attempts": len(q.attempts), **logic.links(q)} for q in quizzes]


@mcp.tool
def get_quiz_results(quiz_id: Annotated[int, Field(description="Quiz id from create_quiz/list_quizzes")]) -> dict:
    """Get student scores and per-question stats (how many got each question wrong) for a quiz."""
    with SessionLocal() as s:
        return logic.results_summary(_own_quiz(s, _teacher(s), quiz_id))


@mcp.tool
def update_quiz(
    quiz_id: Annotated[int, Field(description="Quiz to change")],
    title: Annotated[str | None, Field(description="New title")] = None,
    time_limit_min: Annotated[int | None, Field(description="New time limit in minutes")] = None,
    status: Annotated[str | None, Field(description="'published' (open) or 'closed' (no more attempts)")] = None,
    questions: Annotated[list[QuestionIn] | None, Field(description="Full replacement list of questions")] = None,
) -> dict:
    """Change a quiz's title, time limit, open/closed status, or replace all its questions."""
    with SessionLocal() as s:
        quiz = _own_quiz(s, _teacher(s), quiz_id)
        if title:
            quiz.title = title.strip()[:200]
        if time_limit_min:
            quiz.time_limit_min = max(1, min(time_limit_min, 180))
        if status in ("published", "closed"):
            quiz.status = status
        if questions:
            logic.replace_questions(s, quiz, [q.model_dump() for q in questions])
        s.commit()
        return {"quiz_id": quiz.id, "title": quiz.title, "status": quiz.status,
                "questions": len(quiz.questions), **logic.links(quiz)}
