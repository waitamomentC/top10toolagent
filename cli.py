#!/usr/bin/env python3
"""top10tool — 热搜 TOP10 智能工具 终端聊天界面"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

# Windows 终端 UTF-8
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

console = Console(highlight=False)
CONFIG_DIR = Path.home() / ".top10tool"
CONFIG_FILE = CONFIG_DIR / "config.json"
PACKAGE_DIR = Path(__file__).resolve().parent  # agent/ 目录

# ── 红色扳手 ASCII ──
WRENCH = r"""[red]
    ▐███▌
   ███████
   ██   ██
   ██   ██
   ██   ██
   ███████
    █████
     ███
     ███
     ███
     ███
     ███
     ███
    █████
   ███████
  █████████[/red]"""

HEADER = Panel(
    WRENCH + "\n[bold white]top10tool[/bold white]",
    subtitle="[dim]热搜 TOP10 智能工具[/dim]",
    border_style="red",
    padding=(1, 4),
)


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
    console.print()
    console.print("🔧 [bold]首次运行 — 请配置 LLM 连接信息[/bold]")
    console.print("[dim]支持平台: OpenAI / DeepSeek / 阿里百炼 / Ollama 等[/dim]")
    console.print("[dim]格式: OpenAI 兼容 API[/dim]")
    console.print()

    base_url = input("  API 地址 (BASE_URL): ").strip()
    if not base_url:
        base_url = "https://api.deepseek.com"
        console.print(f"  [dim]→ 使用默认: {base_url}[/dim]")

    api_key = input("  API Key: ").strip()
    while not api_key:
        console.print("  [red]⚠️  API Key 不能为空[/red]")
        api_key = input("  API Key: ").strip()

    model = input("  模型名称 (如 deepseek-chat, gpt-4o-mini): ").strip()
    if not model:
        model = "deepseek-chat"
        console.print(f"  [dim]→ 使用默认: {model}[/dim]")

    cfg = {"llm_base_url": base_url, "llm_api_key": api_key, "llm_model": model}
    save_config(cfg)
    console.print(f"\n[green]✅ 配置已保存到 {CONFIG_FILE}[/green]\n")
    return cfg


def _render_crawl_event(ev: dict) -> None:
    """渲染爬虫实时进度事件"""
    phase = ev.get("phase", "")
    if phase == "search":
        console.print(f"    [bold cyan]🔍[/bold cyan] [dim]{ev['message']}[/dim]")
    elif phase == "fetch":
        url_short = ev["url"][:80]
        status = ev["status"]
        page_num = ev.get("page_num", 0)
        title = (ev.get("title") or "")[:50]
        if status == "ok":
            rel = "★" if ev.get("relevant") else " "
            console.print(f"    [green]✓[/green] [{page_num}] {rel} [dim]{title}[/dim] [dim]({url_short})[/dim]")
        elif status == "blocked":
            console.print(f"    [red]⊘[/red] [{page_num}] [dim]被拦截: {url_short}[/dim]")
        elif status == "fail":
            console.print(f"    [dim]⊘ [{page_num}] 不符合条件: {url_short}[/dim]")


async def chat_loop(cfg: dict) -> None:
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

    # ── 聊天界面头部 ──
    console.print(HEADER)
    console.print(f"  [dim]模型: {cfg['llm_model']}  ·  工具: {reg.tool_names()}[/dim]")
    console.print(f"  [dim]{'─' * 56}[/dim]")
    console.print()

    while True:
        try:
            query = console.input(f"[bold blue]>[/bold blue] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n  👋 再见\n")
            break

        if not query:
            continue
        if query.lower() in ("/exit", "/quit", "/q"):
            console.print("  👋 再见\n")
            break
        if query.lower() == "/config":
            console.print(f"  [dim]模型: {cfg['llm_model']}[/dim]")
            console.print(f"  [dim]API:  {cfg['llm_base_url']}[/dim]")
            console.print()
            continue
        if query.lower() == "/uninstall":
            console.print(f"  [dim]卸载: pip uninstall top10tool -y[/dim]")
            console.print(f"  [dim]配置: {CONFIG_FILE}（手动删除）[/dim]")
            console.print()
            continue
        if query.lower() == "/modify":
            cfg = setup_wizard()
            llm = OpenAILLM(
                api_key=cfg["llm_api_key"],
                base_url=cfg["llm_base_url"],
                model=cfg["llm_model"],
            )
            router = ReActRouter(llm=llm, registry=reg)
            console.print(f"  [green]✅ 配置已更新: {cfg['llm_model']}[/green]\n")
            continue

        # ── 问候语拦截 ──
        greeting = re.match(
            r"^(你好|您好|嗨|hi|hello|hey|早|早上好|中午好|晚上好|下午好|在吗|在不在|在不)[!！。.～~]*$",
            query, re.IGNORECASE
        )
        if greeting:
            console.print()
            console.print(Markdown(
                "你好！👋 我是 **top10tool**，热搜 TOP10 智能助手。\n\n"
                "输入「**当日抖音热搜**」「**当日微博热搜**」等指令开始爬取热搜数据。\n"
                "也可以直接跟我聊天，或输入算式让我计算。"
            ))
            console.print()
            continue

        # ── 流式执行 Agent ──
        console.print()
        answer = ""
        tools_used: list[str] = []
        try:
            async for ev in router.run_stream(query, max_steps=12):
                if ev["type"] == "step" and ev["status"] == "running":
                    thought_short = ev["thought"][:60].replace("\n", " ")
                    console.print(
                        f"  [yellow]●[/yellow] [{ev['step']}] "
                        f"[dim]{thought_short}[/dim] "
                        f"→ [bold]{ev['action']}[/bold] "
                        f"[dim]⏳[/dim]"
                    )
                elif ev["type"] == "tool":
                    obs_preview = ev["result"][:120].replace("\n", " ")
                    console.print(
                        f"  [green]✓[/green] [{ev['step']}] "
                        f"[dim]{ev['tool']} → {obs_preview}[/dim]"
                    )
                    tools_used.append(ev["tool"])
                elif ev["type"] == "crawl":
                    _render_crawl_event(ev)
                elif ev["type"] == "step" and ev["status"] == "done":
                    pass  # tool result already shown
                elif ev["type"] == "done":
                    answer = ev["answer"]

        except Exception as e:
            console.print(f"  [red]出错: {e}[/red]\n")
            continue

        # 回复内容
        if answer:
            console.print()
            console.print(Markdown(answer))

        # 工具调用汇总
        if tools_used:
            tags = "  ".join(
                f"[yellow]●[/yellow] [bold]{t}[/bold]" for t in tools_used
            )
            console.print(f"\n  [dim]{tags}[/dim]")

        console.print()


REPO_PATH_FILE = CONFIG_DIR / "repo_path"
INSTALLED_COMMIT_FILE = CONFIG_DIR / "installed_commit"


def find_repo_dir() -> Path | None:
    """定位 git 仓库根目录"""
    # ① 优先读取安装时保存的路径
    if REPO_PATH_FILE.exists():
        saved = Path(REPO_PATH_FILE.read_text(encoding="utf-8").strip())
        if (saved / ".git").exists():
            return saved

    # ② 尝试当前目录 + 包目录的父级链
    for start in [Path.cwd(), PACKAGE_DIR]:
        d = start.resolve()
        for _ in range(6):
            if (d / ".git").exists():
                _save_repo_path(d)
                return d
            if d.parent == d:
                break
            d = d.parent

    return None


def _save_repo_path(path: Path) -> None:
    """保存仓库路径，方便下次快速定位"""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        REPO_PATH_FILE.write_text(str(path.resolve()), encoding="utf-8")
    except Exception:
        pass


def _get_remote_commit(repo: Path) -> str | None:
    """获取 origin/master 的 commit hash"""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "origin/master"],
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout.strip()
    except Exception:
        return None


def _save_installed_commit(repo: Path) -> None:
    """pip 安装后保存当前版本 hash"""
    commit = _get_remote_commit(repo)
    if commit:
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            INSTALLED_COMMIT_FILE.write_text(commit, encoding="utf-8")
        except Exception:
            pass


def check_for_updates() -> bool:
    """对比已安装版本 vs 远程最新，有更新则提示。返回 True 表示可继续。"""
    repo = find_repo_dir()
    if repo is None:
        return True

    console.print(f"  [dim]检查更新...[/dim]")
    try:
        subprocess.run(
            ["git", "fetch", "origin"],
            cwd=str(repo),
            capture_output=True,
            timeout=15,
        )
    except Exception:
        return True

    remote_commit = _get_remote_commit(repo)
    if not remote_commit:
        return True

    installed_commit = ""
    if INSTALLED_COMMIT_FILE.exists():
        installed_commit = INSTALLED_COMMIT_FILE.read_text(encoding="utf-8").strip()

    if installed_commit == remote_commit:
        console.print(f"  [dim]已是最新版本 ✓[/dim]")
        return True

    # 有更新 → 展示并询问
    behind_desc = ""
    try:
        if installed_commit:
            result = subprocess.run(
                ["git", "rev-list", "--count", f"{installed_commit}..origin/master"],
                cwd=str(repo),
                capture_output=True,
                text=True,
                timeout=10,
            )
            behind = result.stdout.strip()
            behind_desc = f"{behind} 个提交"
        else:
            behind_desc = "新安装"
    except Exception:
        pass

    try:
        log = subprocess.run(
            ["git", "log", "--oneline", f"origin/master", "-n", "5"],
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=10,
        )
        new_commits = log.stdout.strip()
    except Exception:
        new_commits = behind_desc

    console.print()
    console.print(f"  [bold yellow]⚡ 发现新版本 ({behind_desc}):[/bold yellow]")
    console.print(f"  [dim]{new_commits}[/dim]")
    console.print()
    choice = input("  是否更新? [Y/n]: ").strip().lower()
    if choice not in ("", "y", "yes"):
        console.print("  [dim]跳过更新[/dim]\n")
        return True

    # 执行更新
    try:
        subprocess.run(["git", "pull"], cwd=str(repo), check=True, timeout=30)
        console.print(f"  [green]✅ git pull 完成[/green]")
    except Exception as e:
        console.print(f"  [red]git pull 失败: {e}[/red]\n")
        return True

    # pip reinstall
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--force-reinstall", "--no-deps", str(repo)],
            check=True,
            timeout=120,
        )
        console.print(f"  [green]✅ pip 重装完成[/green]")
        _save_installed_commit(repo)
    except Exception as e:
        console.print(f"  [red]pip 重装失败: {e}[/red]")
        console.print(f"  [dim]请手动: pip install --force-reinstall {repo}[/dim]\n")
        return True

    console.print()
    console.print("  [bold yellow]⚠ 更新完成，请重新启动 top10tool[/bold yellow]")
    console.print()
    return False  # 需要重启


def main():
    cfg = load_config()
    if cfg is None:
        cfg = setup_wizard()

    if not check_for_updates():
        return  # 更新后需重启

    import asyncio
    asyncio.run(chat_loop(cfg))


if __name__ == "__main__":
    main()
