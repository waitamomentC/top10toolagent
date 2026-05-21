from __future__ import annotations

from pydantic import BaseModel, Field


# ── 网关层: 请求 / 响应 ──────────────────────────────────────────────

class AgentRequest(BaseModel):
    query: str = Field(..., description="用户输入的问题")
    max_steps: int = Field(default=10, ge=1, le=50, description="ReAct 最大步数")
    stream: bool = Field(default=False, description="是否流式输出")


class AgentResponse(BaseModel):
    answer: str
    steps: list[AgentStep] = Field(default_factory=list)
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)


class AgentStep(BaseModel):
    step: int
    thought: str
    action: str | None = None
    action_input: str | None = None
    observation: str | None = None


class ToolCallRecord(BaseModel):
    tool_name: str
    arguments: str
    result: str


# ── 路由层: ReAct 内部结构 ───────────────────────────────────────────

class ThoughtAction(BaseModel):
    """LLM 返回的 Thought + Action 解析结果"""
    thought: str
    action: str | None = None       # None 表示 Final Answer
    action_input: str | None = None


# ── 工具层: 通用结构 ─────────────────────────────────────────────────

class ToolResult(BaseModel):
    success: bool
    data: str
    error: str | None = None
