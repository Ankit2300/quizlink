"""Phase 2 check against the running server: Claude-style MCP call over HTTP, then a student takes the quiz."""
import asyncio
import re
import urllib.parse
import urllib.request

from fastmcp import Client

BASE = "http://localhost:8000"


async def main():
    async with Client(f"{BASE}/mcp?key=demo") as c:
        r = (await c.call_tool("create_quiz", {
            "title": "Class 6 - Fractions", "time_limit_min": 10,
            "questions": [
                {"text": "1/2 + 1/4 = ?", "options": ["1/6", "3/4", "2/6", "1/8"], "correct_index": 1,
                 "topic": "Adding", "explanation": "1/2 = 2/4, so 2/4 + 1/4 = 3/4."},
                {"text": "Which is bigger?", "options": ["1/3", "1/5"], "correct_index": 0, "topic": "Comparing"},
                {"text": "2/4 equals?", "options": ["1/2", "1/4", "2/8"], "correct_index": 0, "topic": "Equivalent"},
            ]})).data
    print("MCP over HTTP OK:", r["student_url"])
    code = r["student_url"].rsplit("/", 1)[1]
    page = urllib.request.urlopen(f"{BASE}/q/{code}").read().decode()
    qids = re.findall(r'name="q_(\d+)"', page)
    qids = list(dict.fromkeys(qids))
    print("Student page OK, questions:", len(qids), "timer:", "id=\"timer\"" in page)
    # student answers Q1 right, Q2 wrong, skips Q3
    data = urllib.parse.urlencode({"student_name": "Aarav", f"q_{qids[0]}": "1", f"q_{qids[1]}": "1"}).encode()
    res = urllib.request.urlopen(urllib.request.Request(f"{BASE}/q/{code}", data=data))
    html = res.read().decode()
    print("Redirected to:", res.url)
    print("Score shown:", re.search(r"(\d+) / (\d+)", html).group(0), "| expected 1 / 3")
    print("Explanation shown:", "3/4" in html and "Not answered" in html)
    async with Client(f"{BASE}/mcp?key=demo") as c:
        res = (await c.call_tool("get_quiz_results", {"quiz_id": r["quiz_id"]})).data
    print("Results via MCP:", res["attempts"], "attempt(s), avg", res["average_percent"], "%",
          [(q["number"], q["students_wrong"]) for q in res["per_question"]])

asyncio.run(main())
