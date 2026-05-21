from __future__ import annotations

from abc import ABC, abstractmethod

from models.schemas import ToolResult


class BaseTool(ABC):
    """工具基类 —— 所有工具继承此类"""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @abstractmethod
    async def execute(self, input_str: str) -> ToolResult: ...

    def format_for_prompt(self) -> str:
        return f"- {self.name}: {self.description}"
