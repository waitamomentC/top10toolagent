"""直接测试 ReAct Agent（绕过 HTTP，避免编码问题）"""
import asyncio
import io
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# 环境变量请在终端中设置:
# export LLM_API_KEY="sk-xxx"
# export LLM_BASE_URL="https://api.deepseek.com"
# export LLM_MODEL="deepseek-v4-flash"

from core.llm import OpenAILLM
from router.react_router import ReActRouter
from tools.registry import ToolRegistry
from tools.builtin import CalculatorTool, DateTimeTool, WebSearchTool
from tools.excel import ReadExcelTool, WriteExcelTool
from tools.web_scraper import WebScraperTool
from tools.web_crawler import WebCrawlerTool

async def main():
    reg = ToolRegistry()
    reg.register(DateTimeTool())
    reg.register(CalculatorTool())
    reg.register(WebSearchTool())
    reg.register(ReadExcelTool())
    reg.register(WriteExcelTool())
    reg.register(WebScraperTool())
    reg.register(WebCrawlerTool())

    llm = OpenAILLM(
        api_key=os.environ["LLM_API_KEY"],
        base_url=os.environ["LLM_BASE_URL"],
        model=os.environ["LLM_MODEL"],
    )
    router = ReActRouter(llm=llm, registry=reg)

    query = "今天是几号？现在是几点？"
    print(f"Query: {query}")
    print("=" * 50)
    result = await router.run(query, max_steps=5)
    print(f"Answer: {result.answer}")
    print(f"Steps: {len(result.steps)}")
    for s in result.steps:
        print(f"  Step {s.step}: Thought={s.thought[:80]}... Action={s.action} Input={s.action_input} Obs={str(s.observation)[:80]}...")

if __name__ == "__main__":
    asyncio.run(main())
