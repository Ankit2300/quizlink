# QuizLink

**Your Claude writes the test. QuizLink runs it.**

A teacher asks Claude for a quiz (from a topic or a chapter photo). Claude writes the questions and saves them to QuizLink over MCP. QuizLink gives a student link: students take the quiz on their phones, it is marked automatically, and the teacher sees the results. The teacher can edit any question in the app.

**There is no AI inside QuizLink.** No OpenAI/Anthropic keys or libraries. The teacher's own Claude does the thinking; QuizLink does the saving, sharing, marking and reporting.

## Connect to Claude
1. claude.ai → **Settings → Connectors → Add custom connector**
2. Name: `QuizLink` · URL: `<APP_URL>/mcp?key=demo`
3. In a new chat, enable QuizLink in the tools menu and ask:
   *"Make a 10-question quiz for Class 6 on fractions, 15 minutes, and save it to QuizLink."*

## Try the app
- Teacher login: `<APP_URL>/teacher` · `demo@quizlink.test` / `demo1234`
- Open the student link from the dashboard in a private window to take the quiz.

## MCP tools
| Tool | What it does |
|---|---|
| `create_quiz` | Save a quiz Claude wrote; returns student, edit and results links |
| `list_quizzes` | List the teacher's quizzes |
| `update_quiz` | Change title, time limit, open/closed, or questions |
| `get_quiz_results` | Scores + per-question stats, so Claude can explain weak topics |

## Stack
Python · FastAPI · FastMCP (Streamable HTTP at `/mcp`) · SQLAlchemy (SQLite locally, Postgres on Neon) · Render

## Run locally
```
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app:app --port 8000
.venv/bin/python test_phase1.py   # MCP tools
.venv/bin/python test_phase2.py   # student flow (server running)
.venv/bin/python test_phase3.py   # teacher flow (server running)
```
