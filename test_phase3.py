"""Phase 3 check: teacher login, dashboard, edit (change/delete/add question), results, access control."""
import re
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar

BASE = "http://localhost:8000"
anon = urllib.request.build_opener()
t = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))


def post(op, path, data):
    return op.open(urllib.request.Request(BASE + path, data=urllib.parse.urlencode(data).encode()))


r = anon.open(BASE + "/teacher")
print("Not logged in -> redirected to login:", r.url.endswith("/teacher/login"))
print("Wrong password rejected:", "Wrong login" in post(t, "/teacher/login", {"login": "demo@quizlink.test", "password": "x"}).read().decode())
r = post(t, "/teacher/login", {"login": "demo@quizlink.test", "password": "demo1234"})
dash = r.read().decode()
print("Login -> dashboard:", r.url.endswith("/teacher"), "| quiz listed:", "Class 6 - Fractions" in dash,
      "| connector URL shown:", "/mcp?key=demo" in dash)

edit = t.open(BASE + "/teacher/quiz/1").read().decode()
ids = re.findall(r'name="q-(\d+)-id" value="(\d+)"', edit)
print("Edit page questions:", len(ids))
# change Q1 text + correct answer, delete Q3, add a new Q
data = {"title": "Class 6 - Fractions (edited)", "description": "", "time_limit_min": "12", "status": "published",
        "q-0-id": ids[0][1], "q-0-text": "1/2 + 1/4 = ? (edited)", "q-0-opt-0": "1/6", "q-0-opt-1": "3/4",
        "q-0-opt-2": "2/6", "q-0-opt-3": "1/8", "q-0-correct": "1",
        "q-1-id": ids[1][1], "q-1-text": "Which is bigger?", "q-1-opt-0": "1/3", "q-1-opt-1": "1/5", "q-1-correct": "0",
        "q-2-id": ids[2][1], "q-2-text": "2/4 equals?", "q-2-opt-0": "1/2", "q-2-opt-1": "1/4", "q-2-correct": "0",
        "q-2-delete": "1",
        "q-3-id": "", "q-3-text": "3/3 = ?", "q-3-opt-0": "0", "q-3-opt-1": "1", "q-3-opt-2": "3", "q-3-correct": "1"}
r = post(t, "/teacher/quiz/1", data)
page = r.read().decode()
print("Saved:", "Saved." in page, "| new title:", "(edited)" in page, "| new Q present:", "3/3 = ?" in page,
      "| deleted Q gone:", "2/4 equals?" not in page)
bad = dict(data)
bad.pop("q-3-correct")
print("Missing correct answer rejected:", "tick the correct answer" in post(t, "/teacher/quiz/1", bad).read().decode())

student = anon.open(BASE + "/q/" + re.search(r"/q/(\w+)", page).group(1)).read().decode()
print("Student sees edits:", "(edited)" in student and "3/3 = ?" in student)

res = t.open(BASE + "/teacher/quiz/1/results").read().decode()
print("Results page: Aarav listed:", "Aarav" in res, "| per-question table:", "Question by question" in res)

try:
    anon.open(BASE + "/teacher/quiz/1/results")
    print("Results without login: redirected to login")
except urllib.error.HTTPError as e:
    print("Results without login blocked:", e.code)
