from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.llm import OpenAILLM
from gateway.handler import AgentGateway
from models.schemas import AgentRequest, AgentResponse
from router.react_router import ReActRouter
from tools.builtin import CalculatorTool, DateTimeTool, WebSearchTool
from tools.excel import ReadExcelTool, WriteExcelTool
from tools.registry import ToolRegistry
from tools.web_scraper import WebScraperTool
from tools.web_crawler import WebCrawlerTool
from tools.file_utils import ListExcelFilesTool


# ── 依赖注入: 初始化各层 ──────────────────────────────────────────────

def _build_registry() -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(CalculatorTool())
    reg.register(DateTimeTool())
    reg.register(WebSearchTool())
    reg.register(ReadExcelTool())
    reg.register(WriteExcelTool())
    reg.register(WebScraperTool())
    reg.register(WebCrawlerTool())
    reg.register(ListExcelFilesTool())
    return reg


def _build_llm() -> OpenAILLM:
    return OpenAILLM(
        api_key=os.getenv("LLM_API_KEY", "sk-your-key"),
        base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
        model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
    )


registry = _build_registry()
llm = _build_llm()
react_router = ReActRouter(llm=llm, registry=registry)
gateway = AgentGateway(router=react_router)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期 —— 启动/关闭时的钩子"""
    yield


app = FastAPI(
    title="ReAct Agent",
    description="基于 ReAct 范式的智能 Agent —— 网关层 / 路由层 / 工具层 清晰分层",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── 入口层: API ──────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "tools": registry.tool_names()}


@app.post("/agent/run", response_model=AgentResponse)
async def agent_run(req: AgentRequest):
    """执行 ReAct Agent"""
    return await gateway.handle(req)
