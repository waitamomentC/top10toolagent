from __future__ import annotations

import asyncio
import datetime as dt
import math

from models.schemas import ToolResult
from tools.base import BaseTool


class CalculatorTool(BaseTool):
    name = "calculator"
    description = "执行数学计算。输入一个数学表达式，返回计算结果。支持 + - * / ** sqrt() sin() cos() 等。"

    async def execute(self, input_str: str) -> ToolResult:
        try:
            allowed = {"__builtins__": {}} | {
                k: getattr(math, k)
                for k in dir(math)
                if not k.startswith("_")
            }
            result = eval(input_str.strip(), allowed, {})
            return ToolResult(success=True, data=str(result))
        except Exception as e:
            return ToolResult(success=False, data="", error=str(e))


class DateTimeTool(BaseTool):
    name = "datetime"
    description = "获取当前日期时间。输入 'now' 返回完整时间，输入 'date' 返回日期，输入 'time' 返回时间。"

    async def execute(self, input_str: str) -> ToolResult:
        now = dt.datetime.now()
        mapping = {
            "now": now.strftime("%Y-%m-%d %H:%M:%S"),
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
        }
        data = mapping.get(input_str.strip().lower(), mapping["now"])
        return ToolResult(success=True, data=data)


class WebSearchTool(BaseTool):
    name = "web_search"
    description = (
        "联网搜索。输入搜索关键词，返回搜索结果列表（标题、URL、摘要）。"
        "用于获取实时信息、验证事实、查找最新资讯等。"
    )

    async def execute(self, input_str: str) -> ToolResult:
        q = input_str.strip()
        results = await _duckduckgo_search(q)
        if not results:
            return ToolResult(success=False, data="", error=f"关键词 '{q}' 无搜索结果")
        lines = [f"搜索: {q}", ""]
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r['title']}")
            lines.append(f"   {r['url']}")
            lines.append(f"   {r['snippet']}")
            lines.append("")
        return ToolResult(success=True, data="\n".join(lines))


async def _duckduckgo_search(keyword: str, max_results: int = 10) -> list[dict]:
    """DuckDuckGo 搜索，返回 [{title, url, snippet}, ...]"""
    # 方案 A: ddgs (新版)
    try:
        from ddgs import DDGS
        loop = asyncio.get_running_loop()
        raw = await loop.run_in_executor(
            None,
            lambda: list(DDGS().text(keyword, max_results=max_results)),
        )
        return [
            {"title": r["title"], "url": r["href"], "snippet": r.get("body", "")}
            for r in raw if r.get("href")
        ]
    except Exception:
        pass

    # 方案 B: duckduckgo_search (旧版)
    try:
        from duckduckgo_search import DDGS
        loop = asyncio.get_running_loop()
        raw = await loop.run_in_executor(
            None,
            lambda: list(DDGS().text(keyword, max_results=max_results)),
        )
        return [
            {"title": r["title"], "url": r["href"], "snippet": r.get("body", "")}
            for r in raw if r.get("href")
        ]
    except Exception:
        pass

    return []
