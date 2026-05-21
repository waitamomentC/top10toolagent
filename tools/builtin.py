from __future__ import annotations

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
    name = "search"
    description = "搜索互联网信息。输入搜索关键词，返回模拟搜索结果。（生产环境请接入真实搜索 API）"

    async def execute(self, input_str: str) -> ToolResult:
        # 模拟搜索 —— 生产环境接入 SerpAPI / Tavily / Bing 等
        q = input_str.strip()
        mock = {
            "天气": f"'{q}' 搜索结果: 今日多云转晴，气温 22-28°C，空气质量良。",
            "新闻": f"'{q}' 搜索结果: 今日头条 —— AI 技术持续突破，各大厂商加速布局。",
        }
        data = mock.get(q, f"'{q}' 的搜索结果: 这是一个模拟搜索返回。请在生产中接入真实搜索引擎。")
        return ToolResult(success=True, data=data)
