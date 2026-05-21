from __future__ import annotations

from tools.base import BaseTool


class ToolRegistry:
    """工具注册表 —— 管理所有可用工具"""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def list_tools(self) -> list[BaseTool]:
        return list(self._tools.values())

    def format_prompt(self) -> str:
        """生成 ReAct prompt 中的工具描述"""
        return "\n".join(t.format_for_prompt() for t in self._tools.values())

    def tool_names(self) -> str:
        return ", ".join(self._tools.keys())
