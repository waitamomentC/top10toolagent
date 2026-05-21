"""测试完整工作流: 格式校验 → ReAct → Excel"""
import asyncio, sys, io, os
sys.path.insert(0, "F:/project/项目二 GEO网页人工搬运/agent")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# 环境变量请在终端中设置

from core.llm import OpenAILLM
from gateway.handler import AgentGateway
from models.schemas import AgentRequest
from router.react_router import ReActRouter
from tools.registry import ToolRegistry
from tools.builtin import CalculatorTool, DateTimeTool, WebSearchTool
from tools.excel import ReadExcelTool, WriteExcelTool
from tools.web_scraper import WebScraperTool
from tools.web_crawler import WebCrawlerTool
from tools.file_utils import ListExcelFilesTool


def build():
    reg = ToolRegistry()
    for t in [DateTimeTool(), CalculatorTool(), WebSearchTool(),
              ReadExcelTool(), WriteExcelTool(),
              WebScraperTool(), WebCrawlerTool(), ListExcelFilesTool()]:
        reg.register(t)
    llm = OpenAILLM(api_key=os.environ["LLM_API_KEY"],
                    base_url=os.environ["LLM_BASE_URL"],
                    model=os.environ["LLM_MODEL"])
    gateway = AgentGateway(router=ReActRouter(llm=llm, registry=reg))
    return gateway


async def test(query: str, label: str):
    print(f"\n{'='*60}")
    print(f"[{label}]  Query: {query}")
    req = AgentRequest(query=query, max_steps=12)
    result = await build().handle(req)
    print(f"Answer: {result.answer}")
    print(f"Steps: {len(result.steps)}, Tools: {len(result.tool_calls)}")
    for s in result.steps:
        print(f"  S{s.step}: {s.action or 'FINAL'} | {str(s.observation)[:100] if s.observation else ''}")
    return result


async def main():
    # 测试 1: 非法格式 → 网关直接打回
    await test("今天有什么热搜", "格式校验-非法")

    # 测试 2: 笼统关键词 → LLM 反问
    await test("当日AI热搜", "笼统关键词-AI")

    # 测试 3: 正确格式 → 完整流程
    await test("当日抖音热搜", "正确格式-抖音")

if __name__ == "__main__":
    asyncio.run(main())
