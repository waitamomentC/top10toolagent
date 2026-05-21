from __future__ import annotations

import re

from core.llm import BaseLLM
from models.schemas import AgentResponse, AgentStep, ThoughtAction, ToolCallRecord
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
调用 datetime 工具获取当前精确日期，将"当日"替换为具体日期（如 2026年5月22日）。

### 步骤 3: 搜索热搜
使用 web_crawler 工具，关键词格式：「XXX热榜 YYYY年M月D日」
爬取后从结果中提取每条热搜的：日期、关键词（从内容中提炼）、链接（URL）、热度、内容简述。
过滤规则：热度低于 800 万的不录入。最终结果至少 10 条，最多 20 条。

### 步骤 4: 确认 Excel 文件
调用 list_excel_files 工具查看项目根目录（agent 的父目录）下已有的 Excel 文件。
- 如果没有文件 → 以平台英文名在项目根目录创建新文件（如 抖音→../douyin_trending.xlsx, 微博→../weibo_trending.xlsx）
- 如果有文件 → 在 Final Answer 中列出文件名，让用户选择要写入哪个文件
- 用户选择后，在下一轮对话中用选定的文件写入

### 步骤 5: 写入 Excel
检查已提取的热搜数据：
- 如果不足 10 条 → 继续爬取更多页面（调整关键词或增加深度）
- 过滤掉热度低于 800 万的数据
- 保留 10~20 条（热度从高到低取前 20）
使用 write_excel 工具写入。文件路径必须使用 ../文件名.xlsx。JSON 格式：
{{"file":"../douyin_trending.xlsx", "sheet":"热搜", "data":[["日期","关键字","链接","内容"],["2026-05-22","关键字1","https://...","内容简述"],...]}}
表头固定为四列：日期 | 关键字 | 链接 | 内容
写入成功后告知用户文件路径及实际写入条数。

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
- Action 和 Action Input 必须严格按格式，每次只调用一个工具。
- 工具返回结果后，根据结果决定下一步。
- 如果工具执行失败，思考替代方案。
- 不要跳过步骤 1 的平台具体性判断。
- 写入 Excel 前必须先确认文件（步骤 4）。"""


class ReActRouter:
    """路由层 —— ReAct 循环引擎"""

    def __init__(self, llm: BaseLLM, registry: ToolRegistry) -> None:
        self.llm = llm
        self.registry = registry

    async def run(self, query: str, max_steps: int = 10) -> AgentResponse:
        messages: list[dict] = [
            {"role": "system", "content": SYSTEM_PROMPT.format(tools=self.registry.format_prompt())},
            {"role": "user", "content": query},
        ]

        steps: list[AgentStep] = []
        tool_calls: list[ToolCallRecord] = []

        for i in range(1, max_steps + 1):
            raw = await self.llm.chat(messages)
            parsed = self._parse(raw)

            # 记录步骤
            step = AgentStep(
                step=i,
                thought=parsed.thought,
                action=parsed.action,
                action_input=parsed.action_input,
            )

            if parsed.action is None:
                # 没有 Action → Final Answer
                step.observation = None
                steps.append(step)
                return AgentResponse(
                    answer=parsed.thought or raw,
                    steps=steps,
                    tool_calls=tool_calls,
                )

            # 执行工具
            tool = self.registry.get(parsed.action)
            if tool is None:
                observation = f"错误: 未知工具 '{parsed.action}'。可用: {self.registry.tool_names()}"
            elif parsed.action in ("read_excel", "write_excel"):
                # 路由层二次拦截: LLM 生成的 Excel 操作也做格式校验
                from tools.excel import detect_forbidden_format

                fmt_err = detect_forbidden_format(parsed.action_input or "")
                if fmt_err:
                    observation = fmt_err
                else:
                    result = await tool.execute(parsed.action_input or "")
                    observation = result.data if result.success else f"工具执行失败: {result.error}"
                    tool_calls.append(
                        ToolCallRecord(
                            tool_name=parsed.action,
                            arguments=parsed.action_input or "",
                            result=observation,
                        )
                    )
            else:
                result = await tool.execute(parsed.action_input or "")
                observation = result.data if result.success else f"工具执行失败: {result.error}"
                tool_calls.append(
                    ToolCallRecord(
                        tool_name=parsed.action,
                        arguments=parsed.action_input or "",
                        result=observation,
                    )
                )

            step.observation = observation
            steps.append(step)

            # 将本轮 Thought/Action/Observation 反馈给 LLM
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content": f"Observation: {observation}"})

        # 达到最大步数
        final_raw = await self.llm.chat(
            messages
            + [
                {
                    "role": "user",
                    "content": "已达到最大步数限制，请直接给出 Final Answer。",
                }
            ]
        )
        parsed = self._parse(final_raw)
        return AgentResponse(
            answer=parsed.thought or final_raw,
            steps=steps,
            tool_calls=tool_calls,
        )

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
