"""文件管理工具 —— 列出目录下 Excel 文件"""
from __future__ import annotations

import os
from pathlib import Path

from models.schemas import ToolResult
from tools.base import BaseTool


class ListExcelFilesTool(BaseTool):
    name = "list_excel_files"
    description = (
        "列出上层项目目录（agent 的父目录）下的所有 Excel 文件（.xlsx / .xls）。"
        "输入为空字符串即可，返回文件名列表。"
    )

    async def execute(self, input_str: str) -> ToolResult:
        cwd = Path.cwd().parent  # agent 的父目录 = 项目根目录
        files = sorted(
            [f.name for f in cwd.glob("*.xlsx")] + [f.name for f in cwd.glob("*.xls")]
        )
        if not files:
            return ToolResult(
                success=True,
                data=f"项目根目录 ({cwd}) 下没有 Excel 文件。需要新建一个。",
            )
        lines = [f"项目根目录 ({cwd}) 下的 Excel 文件:"]
        for i, f in enumerate(files, 1):
            lines.append(f"  {i}. {f}")
        return ToolResult(success=True, data="\n".join(lines))
