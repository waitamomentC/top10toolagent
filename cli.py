#!/usr/bin/env python3
"""top10tool — 终端 ReAct Agent 交互工具"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Windows 终端 UTF-8 编码修复
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# 项目根目录加入 path
sys.path.insert(0, str(Path(__file__).resolve().parent))

CONFIG_DIR = Path.home() / ".top10tool"
CONFIG_FILE = CONFIG_DIR / "config.json"

BANNER = r"""
   ╔══════════════════════════════════════╗
   ║  ████████╗ ██████╗ ██████╗  ██╗ ██████╗  ║
   ║  ╚══██╔══╝██╔═══██╗██╔══██╗███║ ╚════██╗ ║
   ║     ██║   ██║   ██║██████╔╝╚██║  █████╔╝ ║
   ║     ██║   ██║   ██║██╔═══╝  ██║  ╚═══██╗ ║
   ║     ██║   ╚██████╔╝██║      ██║ ██████╔╝ ║
   ║     ╚═╝    ╚═════╝ ╚═╝      ╚═╝ ╚═════╝  ║
   ║        🔧 热搜 TOP10 智能工具 🔧         ║
   ╚══════════════════════════════════════╝
"""


def load_config() -> dict | None:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return None


def save_config(cfg: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    os.chmod(CONFIG_FILE, 0o600)


def setup_wizard() -> dict:
    """首次运行: 引导用户配置 LLM"""
    print("\n🔧 首次运行 — 请配置 LLM 连接信息\n")

    print("支持平台: OpenAI / DeepSeek / 阿里百炼 / Ollama 等")
    print("格式: OpenAI 兼容 API\n")

    base_url = input("  API 地址 (BASE_URL): ").strip()
    if not base_url:
        base_url = "https://api.deepseek.com"
        print(f"  → 使用默认: {base_url}")

    api_key = input("  API Key: ").strip()
    while not api_key:
        print("  ⚠️  API Key 不能为空")
        api_key = input("  API Key: ").strip()

    model = input("  模型名称 (如 deepseek-chat, gpt-4o-mini): ").strip()
    if not model:
        model = "deepseek-chat"
        print(f"  → 使用默认: {model}")

    cfg = {"llm_base_url": base_url, "llm_api_key": api_key, "llm_model": model}
    save_config(cfg)
    print(f"\n✅ 配置已保存到 {CONFIG_FILE}\n")
    return cfg


async def repl(cfg: dict) -> None:
    """交互式 ReAct 循环"""
    from core.llm import OpenAILLM
    from router.react_router import ReActRouter
    from tools.builtin import CalculatorTool, DateTimeTool, WebSearchTool
    from tools.excel import ReadExcelTool, WriteExcelTool
    from tools.file_utils import ListExcelFilesTool
    from tools.registry import ToolRegistry
    from tools.web_crawler import WebCrawlerTool
    from tools.web_scraper import WebScraperTool

    reg = ToolRegistry()
    for t in [
        DateTimeTool(), CalculatorTool(), WebSearchTool(),
        ReadExcelTool(), WriteExcelTool(),
        WebScraperTool(), WebCrawlerTool(), ListExcelFilesTool(),
    ]:
        reg.register(t)

    llm = OpenAILLM(
        api_key=cfg["llm_api_key"],
        base_url=cfg["llm_base_url"],
        model=cfg["llm_model"],
    )
    router = ReActRouter(llm=llm, registry=reg)

    print(BANNER)
    print(f"模型: {cfg['llm_model']}  |  工具: {reg.tool_names()}")
    print("输入 '当日XXX热搜' 开始爬取，输入 /exit 退出\n")

    while True:
        try:
            query = input("▶ ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 再见")
            break

        if not query:
            continue
        if query.lower() in ("/exit", "/quit", "/q"):
            print("👋 再见")
            break
        if query.lower() == "/config":
            print(f"  模型: {cfg['llm_model']}")
            print(f"  API:  {cfg['llm_base_url']}")
            continue
        if query.lower() == "/uninstall":
            print(f"  配置文件: {CONFIG_FILE}")
            print(f"  运行卸载脚本以彻底清除：")
            agent_dir = Path(__file__).resolve().parent
            if sys.platform == "win32":
                print(f"    {agent_dir / 'uninstall.bat'}")
            else:
                print(f"    bash {agent_dir / 'uninstall.sh'}")
            continue

        print("⏳ 处理中...", end="\r")
        try:
            result = await router.run(query, max_steps=12)
            print(f"\n{'─' * 50}")
            print(result.answer)
            print(f"{'─' * 50}")
            if result.tool_calls:
                print(f"🔧 调用工具 {len(result.tool_calls)} 次: {', '.join(tc.tool_name for tc in result.tool_calls)}")
            print()
        except Exception as e:
            print(f"\n❌ 出错: {e}\n")


def main():
    cfg = load_config()
    if cfg is None:
        cfg = setup_wizard()

    import asyncio
    asyncio.run(repl(cfg))


if __name__ == "__main__":
    main()
