"""QuizLink web app: student pages, teacher pages, and the MCP endpoint at /mcp. No AI inside."""
from contextlib import asynccontextmanager

import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

import logic
from db import Attempt, Question, Quiz, SessionLocal, Teacher, init_db
from mcp_server import mcp

mcp_app = mcp.http_app(path="/mcp")


@asynccontextmanager
async def lifespan(app):
    init_db()
    async with mcp_app.lifespan(app):
        yield


app = FastAPI(title="QuizLink", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=os.environ.get("SECRET_KEY", "dev-only-change-me"),
                   max_age=60 * 60 * 24 * 14, https_only=logic.BASE_URL.startswith("https"))
templates = Jinja2Templates(directory="templates")


def render(request, name, **ctx):
    return templates.TemplateResponse(request, name, ctx)


def quiz_by_code(s, code) -> Quiz:
    quiz = s.query(Quiz).filter_by(share_code=code).first()
    if not quiz:
        raise HTTPException(404, "Quiz not found")
    return quiz


# ---------- public ----------
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return render(request, "home.html", base_url=logic.BASE_URL)


@app.get("/health")
def health():
    return {"ok": True}


# ---------- student ----------
@app.get("/q/{code}", response_class=HTMLResponse)
def take_quiz(request: Request, code: str):
    with SessionLocal() as s:
        quiz = quiz_by_code(s, code)
        if quiz.status != "published":
            return render(request, "closed.html", quiz=quiz)
        return render(request, "take.html", quiz=quiz, questions=quiz.questions)


@app.post("/q/{code}")
async def submit_quiz(request: Request, code: str):
    form = await request.form()
    name = (form.get("student_name") or "").strip()[:120]
    with SessionLocal() as s:
        quiz = quiz_by_code(s, code)
        if quiz.status != "published":
            return render(request, "closed.html", quiz=quiz)
        if not name:
            return render(request, "take.html", quiz=quiz, questions=quiz.questions,
                          error="Please enter your name.")
        answers = {}
        for q in quiz.questions:
            v = form.get(f"q_{q.id}")
            if v is not None and v.isdigit() and int(v) < len(q.options):
                answers[str(q.id)] = int(v)
        score, total = logic.grade(quiz, answers)
        attempt = Attempt(quiz=quiz, student_name=name, answers=answers, score=score, total=total)
        s.add(attempt)
        s.commit()
        return RedirectResponse(f"/q/{code}/result/{attempt.id}", status_code=303)


@app.get("/q/{code}/result/{attempt_id}", response_class=HTMLResponse)
def quiz_result(request: Request, code: str, attempt_id: int):
    with SessionLocal() as s:
        quiz = quiz_by_code(s, code)
        attempt = s.get(Attempt, attempt_id)
        if not attempt or attempt.quiz_id != quiz.id:
            raise HTTPException(404, "Result not found")
        rows = []
        for q in quiz.questions:
            chosen = attempt.answers.get(str(q.id))
            rows.append({"q": q, "chosen": chosen, "correct": chosen == q.correct_index})
        pct = round(100 * attempt.score / attempt.total) if attempt.total else 0
        return render(request, "result.html", quiz=quiz, attempt=attempt, rows=rows, pct=pct)


# ---------- teacher ----------
class LoginRequired(Exception):
    pass


@app.exception_handler(LoginRequired)
def _login_redirect(request, exc):
    return RedirectResponse("/teacher/login", status_code=303)


def current_teacher(request, s) -> Teacher:
    tid = request.session.get("teacher_id")
    t = s.get(Teacher, tid) if tid else None
    if not t:
        raise LoginRequired()
    return t


def own_quiz(s, teacher, quiz_id) -> Quiz:
    quiz = s.get(Quiz, quiz_id)
    if not quiz or quiz.teacher_id != teacher.id:
        raise HTTPException(404, "Quiz not found")
    return quiz


@app.get("/teacher/login", response_class=HTMLResponse)
def login_page(request: Request):
    return render(request, "login.html")


@app.post("/teacher/login")
async def login(request: Request):
    form = await request.form()
    with SessionLocal() as s:
        t = s.query(Teacher).filter_by(login=(form.get("login") or "").strip().lower()).first()
        if not t or t.password != form.get("password"):
            return render(request, "login.html", error="Wrong login or password.")
        request.session["teacher_id"] = t.id
    return RedirectResponse("/teacher", status_code=303)


@app.get("/teacher/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)


@app.get("/teacher", response_class=HTMLResponse)
def dashboard(request: Request):
    with SessionLocal() as s:
        t = current_teacher(request, s)
        quizzes = s.query(Quiz).filter_by(teacher_id=t.id).order_by(Quiz.created_at.desc()).all()
        rows = [{"quiz": q, "links": logic.links(q), "n": len(q.questions), "attempts": len(q.attempts),
                 "avg": logic.results_summary(q)["average_percent"]} for q in quizzes]
        return render(request, "dashboard.html", teacher=t, rows=rows,
                      mcp_url=f"{logic.BASE_URL}/mcp?key={t.mcp_key}")


@app.get("/teacher/quiz/{quiz_id}", response_class=HTMLResponse)
def edit_page(request: Request, quiz_id: int, saved: int = 0):
    with SessionLocal() as s:
        quiz = own_quiz(s, current_teacher(request, s), quiz_id)
        return render(request, "edit.html", quiz=quiz, questions=quiz.questions, links=logic.links(quiz),
                      saved=saved)


@app.post("/teacher/quiz/{quiz_id}")
async def save_quiz(request: Request, quiz_id: int):
    form = await request.form()
    with SessionLocal() as s:
        quiz = own_quiz(s, current_teacher(request, s), quiz_id)
        by_id = {q.id: q for q in quiz.questions}
        incoming, i = [], 0
        while f"q-{i}-text" in form:
            if not form.get(f"q-{i}-delete") and form.get(f"q-{i}-text", "").strip():
                opts = [form.get(f"q-{i}-opt-{j}", "") for j in range(6)]
                filled = [(j, o.strip()) for j, o in enumerate(opts) if o.strip()]
                c = form.get(f"q-{i}-correct")
                ci = next((k for k, (j, _) in enumerate(filled) if str(j) == c), -1)
                incoming.append({"id": form.get(f"q-{i}-id"), "text": form.get(f"q-{i}-text"),
                                 "options": [o for _, o in filled], "correct_index": ci,
                                 "explanation": form.get(f"q-{i}-explanation", ""),
                                 "topic": form.get(f"q-{i}-topic", "")})
            i += 1
        try:
            clean = logic.validate_questions(incoming)
        except logic.QuizError as e:
            return render(request, "edit.html", quiz=quiz, questions=quiz.questions,
                          links=logic.links(quiz), error=f"{e} (Did you tick the correct answer?)")
        quiz.title = (form.get("title") or quiz.title).strip()[:200]
        quiz.description = (form.get("description") or "").strip()
        try:
            quiz.time_limit_min = max(1, min(int(form.get("time_limit_min") or 15), 180))
        except ValueError:
            pass
        quiz.status = "published" if form.get("status") == "published" else "closed"
        keep = set()
        for pos, (raw, q) in enumerate(zip(incoming, clean)):
            qid = int(raw["id"]) if (raw["id"] or "").isdigit() else None
            row = by_id.get(qid)
            if row:
                keep.add(row.id)
                row.position = pos
                for k, v in q.items():
                    setattr(row, k, v)
            else:
                quiz.questions.append(Question(position=pos, **q))
        for qid, row in by_id.items():
            if qid not in keep:
                quiz.questions.remove(row)
        s.commit()
    return RedirectResponse(f"/teacher/quiz/{quiz_id}?saved=1", status_code=303)


@app.get("/teacher/quiz/{quiz_id}/results", response_class=HTMLResponse)
def results_page(request: Request, quiz_id: int):
    with SessionLocal() as s:
        quiz = own_quiz(s, current_teacher(request, s), quiz_id)
        return render(request, "results.html", quiz=quiz, r=logic.results_summary(quiz),
                      links=logic.links(quiz))


# MCP endpoint (Claude connects to <BASE_URL>/mcp). Mounted last so web routes win.
app.mount("/", mcp_app)
