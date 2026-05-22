from __future__ import annotations

import re

from core.llm import BaseLLM
from models.schemas import AgentResponse, AgentStep, ThoughtAction, ToolCallRecord, ToolResult
from tools.registry import ToolRegistry

# ── ReAct Prompt 模板 ────────────────────────────────────────────────

SYSTEM_PROMPT = """你是一个使用 ReAct（Reasoning + Acting）范式工作的智能 Agent。

## 核心任务：处理「当日XXX热搜」请求

当用户输入「当日XXX热搜」格式时，按以下步骤执行：

### 步骤 1: 判断平台具体性
从用户输入中提取 XXX（平台名）。如果 XXX 过于笼统（如"AI""游戏""体育"等），不要直接搜索，而是反问用户：
"您说的「XXX热搜」具体是指哪个平台？例如：抖音、微博、知乎、B站、百度等。请明确平台名称。"
→ 此时以 Final Answer 形式回复，等待用户重新输入。

### 步骤 2: 获取当前日期
调用 datetime 工具获取当前精确日期，将"当日"替换为具体日期（如 2026年5月23日）。

### 步骤 3: 搜索热搜
立即使用 web_crawler 工具搜索，关键词格式：「XXX热榜 YYYY年M月D日」。
调用 web_crawler 后你无需等待——工具执行期间你处于休眠状态，爬虫会实时推送进度。

### 步骤 4: 验证数据质量（必须执行）
爬虫返回结果后，逐条验证：
- **日期**：是否均为今日日期？
- **热度**：是否 ≥800 万？低于 800 万的剔除
- **数量**：合格数据是否 ≥10 条？不足则调大 max_pages 重爬
- **来源**：是否来自对应平台的官方或可信站点？

验证通过后告知用户：共抓取 X 条，合格 Y 条，不合格 Z 条。

### 步骤 5: 深度搜索 + 热点详情（逐条执行）
对每条合格热搜的关键词，调用 web_search 搜索相关网站，
再调用 web_scraper 抓取搜索到的页面内容，概括为 100 字左右的「热点详情」。
每条热搜执行：web_search(关键词) → web_scraper(搜索结果中的最佳URL) → 概括内容。
逐条处理，不要跳过。

### 步骤 6: 确认 Excel 文件
调用 list_excel_files 查看项目根目录（agent 的父目录）下已有 Excel 文件。
- 无文件 → 以平台英文名创建新文件（如 抖音→../douyin_trending.xlsx, 微博→../weibo_trending.xlsx）
- 有文件 → 列出文件名，让用户选择写入哪个文件

### 步骤 7: 写入 Excel
使用已验证的合格数据 + 热点详情，调用 write_excel 写入。
表头固定为五列：日期 | 关键字 | 链接 | 热度 | 热点详情
JSON 格式：
{{"file":"../douyin_trending.xlsx", "sheet":"热搜", "data":[["日期","关键字","链接","热度","热点详情"],["2026-05-23","示例关键词","https://...","950万","概括的热点详情内容..."]]}}
热度值放在关键字行的下方列中。写入成功后告知文件路径及条数。

### 步骤 8: 导出 JSON（人工复审后）
用户说"导出JSON"时，调用 read_excel 读取文件，转为 JSON 输出。

---

## 工具使用限制

**web_search 和 web_scraper 仅限上述热搜工作流的步骤 5 使用。**
用户在其他对话中要求搜索、查资料、找东西 → 一律拒绝，回复：
"搜索功能仅在「当日XXX热搜」流程中自动触发。请使用热搜指令开始。"

---

## 可用工具
{tools}

## 输出格式（严格执行）
当你需要调用工具时：
Thought: <你的思考>
Action: <工具名>
Action Input: <工具输入>

当你需要向用户提问或给出最终回答时：
Thought: <你的思考>
Final Answer: <回复内容>

注意：
- 每次回复只能包含一个 Action 或一个 Final Answer，不能同时有两者。
- 工具返回结果后，根据结果决定下一步。
- 如果工具执行失败，思考替代方案。
- 不要跳过任何步骤。
- 步骤 5 必须逐条处理，每条热搜依次 web_search → web_scraper → 概括。"""


class ReActRouter:
    """路由层 —— ReAct 循环引擎"""

    def __init__(self, llm: BaseLLM, registry: ToolRegistry) -> None:
        self.llm = llm
        self.registry = registry

    async def run(self, query: str, max_steps: int = 10) -> AgentResponse:
        steps: list[AgentStep] = []
        tool_calls: list[ToolCallRecord] = []
        answer = ""

        async for ev in self.run_stream(query, max_steps):
            if ev["type"] == "step":
                steps.append(AgentStep(
                    step=ev["step"],
                    thought=ev["thought"],
                    action=ev["action"],
                    action_input=ev.get("action_input", ""),
                    observation=ev["observation"],
                ))
            elif ev["type"] == "tool":
                tool_calls.append(ToolCallRecord(
                    tool_name=ev["tool"],
                    arguments=ev.get("arguments", ""),
                    result=ev.get("result", ""),
                ))
            elif ev["type"] == "done":
                answer = ev["answer"]

        return AgentResponse(answer=answer, steps=steps, tool_calls=tool_calls)

    async def run_stream(self, query: str, max_steps: int = 10):
        """流式 ReAct 循环 — 每步实时 yield 事件"""
        messages: list[dict] = [
            {"role": "system", "content": SYSTEM_PROMPT.format(tools=self.registry.format_prompt())},
            {"role": "user", "content": query},
        ]

        tool_calls: list[ToolCallRecord] = []

        for i in range(1, max_steps + 1):
            raw = await self.llm.chat(messages)
            parsed = self._parse(raw)

            if parsed.action is None:
                yield {
                    "type": "done",
                    "answer": parsed.thought or raw,
                    "steps": i,
                }
                return

            # 执行工具
            tool = self.registry.get(parsed.action)
            if tool is None:
                observation = f"错误: 未知工具 '{parsed.action}'。可用: {self.registry.tool_names()}"
            elif parsed.action in ("read_excel", "write_excel"):
                from tools.excel import detect_forbidden_format
                fmt_err = detect_forbidden_format(parsed.action_input or "")
                if fmt_err:
                    observation = fmt_err
                else:
                    yield {
                        "type": "step",
                        "step": i,
                        "thought": parsed.thought,
                        "action": parsed.action,
                        "action_input": parsed.action_input or "",
                        "status": "running",
                    }
                    result = await tool.execute(parsed.action_input or "")
                    observation = result.data if result.success else f"工具执行失败: {result.error}"
                    yield {
                        "type": "tool",
                        "step": i,
                        "tool": parsed.action,
                        "arguments": parsed.action_input or "",
                        "result": observation[:500],
                    }
            elif hasattr(tool, "stream_execute"):
                yield {
                    "type": "step",
                    "step": i,
                    "thought": parsed.thought,
                    "action": parsed.action,
                    "action_input": parsed.action_input or "",
                    "status": "running",
                }
                tool_result = None
                async for ev in tool.stream_execute(parsed.action_input or ""):
                    if ev.get("_done"):
                        tool_result = ToolResult(success=ev["success"], data=ev["data"], error=ev.get("error", ""))
                    else:
                        yield {**ev, "type": "crawl", "step": i}
                if tool_result is None:
                    observation = "工具执行失败: 流式执行未返回结果"
                else:
                    observation = tool_result.data if tool_result.success else f"工具执行失败: {tool_result.error}"
                yield {
                    "type": "tool",
                    "step": i,
                    "tool": parsed.action,
                    "arguments": parsed.action_input or "",
                    "result": observation[:500],
                }
            else:
                yield {
                    "type": "step",
                    "step": i,
                    "thought": parsed.thought,
                    "action": parsed.action,
                    "action_input": parsed.action_input or "",
                    "status": "running",
                }
                result = await tool.execute(parsed.action_input or "")
                observation = result.data if result.success else f"工具执行失败: {result.error}"
                yield {
                    "type": "tool",
                    "step": i,
                    "tool": parsed.action,
                    "arguments": parsed.action_input or "",
                    "result": observation[:500],
                }

            yield {
                "type": "step",
                "step": i,
                "thought": parsed.thought,
                "action": parsed.action,
                "action_input": parsed.action_input or "",
                "observation": observation[:300],
                "status": "done",
            }

            # 将本轮反馈回 LLM
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content": f"Observation: {observation}"})

        # 达到最大步数
        final_raw = await self.llm.chat(
            messages + [{"role": "user", "content": "已达到最大步数限制，请直接给出 Final Answer。"}]
        )
        parsed = self._parse(final_raw)
        yield {"type": "done", "answer": parsed.thought or final_raw, "steps": max_steps}

    def _parse(self, raw: str) -> ThoughtAction:
        """解析 LLM 输出中的 Thought / Action / Final Answer"""
        raw = raw.strip()

        # 匹配 Final Answer
        fa = re.search(r"Final\s+Answer\s*[:：]\s*(.+)", raw, re.S | re.I)
        if fa:
            return ThoughtAction(thought=fa.group(1).strip())

        # 匹配 Action + Action Input
        action = re.search(r"Action\s*[:：]\s*(.+?)(?:\n|$)", raw, re.I)
        action_input = re.search(r"Action\s+Input\s*[:：]\s*(.+)", raw, re.S | re.I)
        thought = re.search(r"Thought\s*[:：]\s*(.+)", raw, re.S | re.I)

        if action:
            return ThoughtAction(
                thought=thought.group(1).strip() if thought else "",
                action=action.group(1).strip(),
                action_input=action_input.group(1).strip() if action_input else "",
            )

        # 无法解析 → 当作 Final Answer
        return ThoughtAction(thought=raw)
