"""Phase 1 check: call the MCP tools the way Claude would (in-memory client)."""
import asyncio
import os

os.environ["DATABASE_URL"] = "sqlite:///./test_quizlink.db"
if os.path.exists("test_quizlink.db"):
    os.remove("test_quizlink.db")

from fastmcp import Client  # noqa: E402

import db  # noqa: E402
from mcp_server import mcp  # noqa: E402

db.init_db()


async def main():
    async with Client(mcp) as c:
        print("TOOLS:", [t.name for t in await c.list_tools()])
        r = await c.call_tool("create_quiz", {
            "title": "Class 6 - Fractions", "time_limit_min": 10,
            "questions": [
                {"text": "1/2 + 1/4 = ?", "options": ["1/6", "3/4", "2/6", "1/8"], "correct_index": 1, "topic": "Adding"},
                {"text": "Which is bigger?", "options": ["1/3", "1/5"], "correct_index": 0, "topic": "Comparing"},
            ]})
        print("CREATE:", r.data)
        print("LIST:", (await c.call_tool("list_quizzes", {})).data)
        try:
            await c.call_tool("create_quiz", {"title": "Bad", "questions": [
                {"text": "x", "options": ["a", "b"], "correct_index": 5}]})
        except Exception as e:
            print("VALIDATION OK:", str(e)[:80])
        print("UPDATE:", (await c.call_tool("update_quiz", {"quiz_id": 1, "time_limit_min": 20})).data)
        print("RESULTS:", (await c.call_tool("get_quiz_results", {"quiz_id": 1})).data)

asyncio.run(main())
