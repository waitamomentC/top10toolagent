from __future__ import annotations

import re

from models.schemas import AgentRequest, AgentResponse
from router.react_router import ReActRouter
from tools.excel import detect_forbidden_format

# "当日XXX热搜" 格式校验
TRENDING_PATTERN = re.compile(r"^当日(.{1,20})热搜$")


class AgentGateway:
    """网关层 —— 请求校验、路由分发、响应封装"""

    def __init__(self, router: ReActRouter) -> None:
        self.router = router

    async def handle(self, req: AgentRequest) -> AgentResponse:
        query = req.query.strip()

        # ── 格式校验: "当日XXX热搜" ───────────────────────────────────
        # 只要 query 里提到了"热搜"/"热榜"相关，就必须匹配格式
        if re.search(r"热搜|热榜", query):
            m = TRENDING_PATTERN.match(query)
            if not m:
                return AgentResponse(
                    answer=(
                        "❌ 输入格式错误。请使用「当日XXX热搜」格式。\n"
                        "例如：当日抖音热搜、当日微博热搜、当日百度热搜\n"
                        "其中 XXX 必须是具体的平台或产品名称，不能过于笼统。"
                    ),
                    steps=[],
                    tool_calls=[],
                )

        # 非 Excel 文件格式拦截
        forbidden = detect_forbidden_format(query)
        if forbidden:
            return AgentResponse(
                answer=forbidden,
                steps=[],
                tool_calls=[],
            )

        return await self.router.run(query=query, max_steps=req.max_steps)
