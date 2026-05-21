from __future__ import annotations

import asyncio
import json
from collections import deque
from dataclasses import dataclass, field

import httpx
from bs4 import BeautifulSoup

from models.schemas import ToolResult
from tools.base import BaseTool
from tools.robots import check_meta_robots, check_robots_header, check_robots_txt, get_crawl_delay
from tools.web_scraper import (
    UA,
    TIMEOUT,
    MAX_CONTENT_LEN,
    _extract_title,
    _extract_time,
    _extract_links,
    _extract_content,
)

# ── 爬虫参数 ──────────────────────────────────────────────────────────

DEFAULT_DEPTH = 1
DEFAULT_MAX_PAGES = 20
DEFAULT_MIN_RELEVANT = 10
SEARCH_RESULTS = 30  # 搜索种子数


@dataclass
class CrawlPage:
    url: str
    title: str
    publish_time: str
    links_text: str
    content: str
    keyword_count: int
    depth: int


@dataclass
class CrawlState:
    keyword: str
    depth: int
    max_pages: int
    min_relevant: int
    visited: set[str] = field(default_factory=set)
    pages: list[CrawlPage] = field(default_factory=list)
    relevant_count: int = 0
    errors: list[str] = field(default_factory=list)
    blocked: int = 0
    blocked_urls: list[str] = field(default_factory=list)


# ── 工具 ──────────────────────────────────────────────────────────────

class WebCrawlerTool(BaseTool):
    name = "web_crawler"
    description = (
        "全网关键词爬虫。输入关键词（或 JSON: {\"keyword\":\"...\", \"depth\":1, \"max_pages\":30}），"
        "通过搜索引擎获取种子 URL，递归爬取匹配页面，提取每页的 发布时间 / 链接 / 正文。"
        f"默认最多爬 {DEFAULT_MAX_PAGES} 页，至少返回 {DEFAULT_MIN_RELEVANT} 个相关结果。"
    )

    async def execute(self, input_str: str) -> ToolResult:
        # ── 解析参数 ──────────────────────────────────────────────────
        kw, depth, max_pages, min_rel = _parse_input(input_str)

        state = CrawlState(
            keyword=kw,
            depth=depth,
            max_pages=max_pages,
            min_relevant=min_rel,
        )

        # ── 第一步: 搜索引擎获取种子 URL ──────────────────────────────
        seed_urls = await _search_keyword(kw)
        if not seed_urls:
            return ToolResult(success=False, data="", error=f"关键词 '{kw}' 搜索无结果")

        # ── 第二步: BFS 爬取 ──────────────────────────────────────────
        queue: deque[tuple[str, int]] = deque((u, 0) for u in seed_urls)

        async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
            while queue and len(state.pages) < state.max_pages:
                url, cur_depth = queue.popleft()
                if url in state.visited:
                    continue
                state.visited.add(url)

                # ── 合规检查: robots.txt ──────────────────────────────────
                allowed, reason = await check_robots_txt(url)
                if not allowed:
                    state.blocked += 1
                    state.blocked_urls.append(f"{url} ({reason})")
                    continue

                # ── 请求间隔: 遵守 robots.txt Crawl-Delay ─────────────────
                delay = get_crawl_delay(url)
                await asyncio.sleep(delay)

                page = await _fetch_and_extract(client, url, state.keyword, cur_depth, state)
                if page is None:
                    continue

                is_relevant = page.keyword_count > 0
                if is_relevant:
                    state.relevant_count += 1

                state.pages.append(page)

                # 如果还不够相关结果数，继续往下挖链接
                if state.relevant_count < state.min_relevant and cur_depth < state.depth:
                    sub_urls = _extract_link_urls(page.links_text)
                    for sub in sub_urls:
                        if len(queue) + len(state.pages) < state.max_pages + 30:
                            queue.append((sub, cur_depth + 1))

                # 提前终止: 达到最小相关数 且 接近上限
                if state.relevant_count >= state.min_relevant and len(state.pages) >= state.max_pages:
                    break

        # ── 第三步: 格式化输出 ────────────────────────────────────────
        if not state.pages:
            return ToolResult(success=False, data="", error=f"关键词 '{kw}' 未爬取到任何页面")

        result = _format_output(state)
        return ToolResult(success=True, data=result)


# ── 解析输入 ──────────────────────────────────────────────────────────

def _parse_input(raw: str) -> tuple[str, int, int, int]:
    raw = raw.strip()
    try:
        params = json.loads(raw)
        if isinstance(params, dict):
            return (
                params.get("keyword", raw),
                int(params.get("depth", DEFAULT_DEPTH)),
                int(params.get("max_pages", DEFAULT_MAX_PAGES)),
                int(params.get("min_relevant", DEFAULT_MIN_RELEVANT)),
            )
    except (json.JSONDecodeError, ValueError):
        pass
    return raw, DEFAULT_DEPTH, DEFAULT_MAX_PAGES, DEFAULT_MIN_RELEVANT


async def _search_keyword(keyword: str) -> list[str]:
    """DuckDuckGo / Bing 搜索 → 种子 URL 列表"""
    # 方案 A: ddgs (新版 duckduckgo_search)
    try:
        from ddgs import DDGS

        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(
            None,
            lambda: list(DDGS().text(keyword, max_results=SEARCH_RESULTS)),
        )
        urls = [r["href"] for r in results if r.get("href")]
        if urls:
            return urls
    except Exception:
        pass

    # 方案 B: 旧版 duckduckgo_search
    try:
        from duckduckgo_search import DDGS

        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(
            None,
            lambda: list(DDGS().text(keyword, max_results=SEARCH_RESULTS)),
        )
        urls = [r["href"] for r in results if r.get("href")]
        if urls:
            return urls
    except Exception:
        pass

    # fallback: 直接抓 DuckDuckGo HTML
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": keyword},
                headers={"User-Agent": UA},
            )
            soup = BeautifulSoup(resp.text, "lxml")
            urls: list[str] = []
            for r in soup.select(".result__url"):
                href = r.get("href", "").strip()
                if href and href.startswith("http"):
                    urls.append(href)
            return urls
    except Exception:
        return []


async def _fetch_and_extract(
    client: httpx.AsyncClient,
    url: str,
    keyword: str,
    depth: int,
    state: CrawlState,
) -> CrawlPage | None:
    """抓取单页 → 提取标题/时间/链接/正文 + 关键词计数"""
    try:
        resp = await client.get(url, headers={"User-Agent": UA, "Accept": "text/html"})
        resp.raise_for_status()
    except Exception:
        return None

    soup = BeautifulSoup(resp.text, "lxml")

    # ── 合规检查: meta robots ─────────────────────────────────────────
    allowed, reason = check_meta_robots(soup)
    if not allowed:
        state.blocked += 1
        state.blocked_urls.append(f"{url} ({reason})")
        return None

    # ── 合规检查: X-Robots-Tag ────────────────────────────────────────
    allowed, reason = check_robots_header(resp.headers)
    if not allowed:
        state.blocked += 1
        state.blocked_urls.append(f"{url} ({reason})")
        return None

    title = _extract_title(soup)
    pub_time = _extract_time(soup)
    content = _extract_content(soup)
    links_text = _extract_links(soup, str(resp.url))

    kw_lower = keyword.lower()
    kw_count = (
        title.lower().count(kw_lower)
        + content.lower().count(kw_lower)
    )

    return CrawlPage(
        url=str(resp.url),
        title=title,
        publish_time=pub_time,
        links_text=links_text,
        content=content,
        keyword_count=kw_count,
        depth=depth,
    )


def _extract_link_urls(links_text: str) -> list[str]:
    """从链接文本中提取纯 URL 列表（用于继续爬）"""
    import re

    urls = re.findall(r"→\s*(https?://\S+)", links_text)
    # 去重，保持顺序
    seen: set[str] = set()
    out: list[str] = []
    for u in urls:
        u = u.rstrip(")")
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


# ── 格式化输出 ────────────────────────────────────────────────────────

def _format_output(state: CrawlState) -> str:
    lines = [
        f"关键词: {state.keyword}",
        f"爬取页面数: {len(state.pages)}  相关页面数: {state.relevant_count}  被拦截: {state.blocked}",
        f"爬取深度: {state.depth}  上限: {state.max_pages}",
        "=" * 50,
        "",
    ]
    if state.blocked_urls:
        lines.append("### 合规拦截（以下页面拒绝被抓取）")
        for b in state.blocked_urls[:20]:
            lines.append(f"  [BLOCKED] {b}")
        if len(state.blocked_urls) > 20:
            lines.append(f"  ... 共 {len(state.blocked_urls)} 条")
        lines.append("")
        lines.append("-" * 40)
        lines.append("")

    for i, p in enumerate(state.pages, 1):
        marker = "★" if p.keyword_count > 0 else "☆"
        lines.append(f"### {marker} 页面 {i}  (深度 {p.depth}, 命中 {p.keyword_count} 次)")
        lines.append(f"URL: {p.url}")
        lines.append(f"标题: {p.title}")
        lines.append(f"发布时间: {p.publish_time}")
        lines.append("")
        lines.append("--- 链接 ---")
        lines.append(p.links_text or "(无链接)")
        lines.append("")
        lines.append("--- 正文 ---")
        lines.append(p.content[:MAX_CONTENT_LEN])
        lines.append("")
        lines.append("-" * 40)
        lines.append("")

    if state.errors:
        lines.append("--- 错误 ---")
        lines.extend(state.errors[:10])

    return "\n".join(lines)
