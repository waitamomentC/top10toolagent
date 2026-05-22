from __future__ import annotations

import asyncio
import json
from collections import deque
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

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

# ── 缓存 ────────────────────────────────────────────────────────────────
CACHE_DIR = Path.home() / ".top10tool"
CACHE_FILE = CACHE_DIR / "crawl_cache.json"

# 常见平台名 → 用于缓存键匹配
_PLATFORM_PATTERNS = [
    "抖音", "微博", "知乎", "bilibili", "B站",
    "百度", "头条", "快手", "小红书", "微信",
    "豆瓣", "虎扑", "贴吧", "天涯", "搜狐",
    "网易", "腾讯", "新浪", "凤凰",
]


def _extract_platform(keyword: str) -> str | None:
    """从搜索关键词中提取平台名"""
    for p in _PLATFORM_PATTERNS:
        if p.lower() in keyword.lower():
            return p
    # fallback: 用关键词本身的前几个字
    return keyword[:6]


def _load_cache() -> dict:
    """加载缓存 {平台名: {urls: [...], updated: '...'}}"""
    try:
        if CACHE_FILE.exists():
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_cache(cache: dict) -> None:
    """保存缓存到文件"""
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def _get_cached_urls(keyword: str) -> list[str]:
    """获取该平台的历史爬取 URL（最近 7 天内有效）"""
    platform = _extract_platform(keyword)
    cache = _load_cache()
    entry = cache.get(platform)
    if not entry:
        return []
    # 检查缓存是否过期（7 天）
    updated = entry.get("updated", "")
    try:
        if updated:
            dt = datetime.fromisoformat(updated)
            age_days = (datetime.now(timezone.utc) - dt).days
            if age_days > 7:
                return []
    except Exception:
        return []
    return entry.get("urls", [])


def _update_cache(keyword: str, urls: list[str]) -> None:
    """更新缓存：追加新 URL，去重，限制数量"""
    platform = _extract_platform(keyword)
    cache = _load_cache()
    existing = set(cache.get(platform, {}).get("urls", []))
    existing.update(urls)
    cache[platform] = {
        "urls": list(existing)[:100],  # 最多 100 条
        "updated": datetime.now(timezone.utc).isoformat(),
    }
    _save_cache(cache)


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
    total_bytes: int = 0
    total_requests: int = 0
    total_time: float = 0.0


# ── 工具 ──────────────────────────────────────────────────────────────

class WebCrawlerTool(BaseTool):
    name = "web_crawler"
    description = (
        "全网关键词爬虫。输入关键词（或 JSON: {\"keyword\":\"...\", \"depth\":1, \"max_pages\":30}），"
        "通过搜索引擎获取种子 URL，递归爬取匹配页面，提取每页的 发布时间 / 链接 / 正文。"
        f"默认最多爬 {DEFAULT_MAX_PAGES} 页，至少返回 {DEFAULT_MIN_RELEVANT} 个相关结果。"
    )

    async def execute(self, input_str: str) -> ToolResult:
        async for ev in self.stream_execute(input_str):
            if ev.get("_done"):
                return ToolResult(**ev)
        return ToolResult(success=False, data="", error="流式执行未返回结果")

    async def stream_execute(self, input_str: str) -> AsyncGenerator[dict, None]:
        """流式爬取 — 实时 yield 进度事件，最后 yield ToolResult 字典（含 _done=True）"""
        kw, depth, max_pages, min_rel = _parse_input(input_str)

        state = CrawlState(
            keyword=kw,
            depth=depth,
            max_pages=max_pages,
            min_relevant=min_rel,
        )

        # ── 第一步: 检查缓存 + 搜索种子 URL ────────────────────────────────
        cached = _get_cached_urls(kw)
        if cached:
            yield {"phase": "search", "message": f"缓存命中 {len(cached)} 个站点，优先爬取", "keyword": kw, "cached": len(cached)}

        yield {"phase": "search", "message": f"正在搜索关键词「{kw}」...", "keyword": kw}
        seed_urls = await _search_keyword(kw)
        if not seed_urls and not cached:
            yield {"success": False, "data": "", "error": f"关键词 '{kw}' 搜索无结果", "_done": True}
            return
        total_seeds = len(cached) + len(seed_urls)
        yield {"phase": "search", "message": f"共获取 {total_seeds} 个种子页面（缓存 {len(cached)} + 搜索 {len(seed_urls)}）", "found": total_seeds}

        # 缓存 URL 优先
        all_seeds: list[str] = []
        seen_seeds: set[str] = set()
        for u in cached:
            if u not in seen_seeds:
                all_seeds.append(u)
                seen_seeds.add(u)
        for u in seed_urls:
            if u not in seen_seeds:
                all_seeds.append(u)
                seen_seeds.add(u)

        # ── 第二步: BFS 爬取 ─────────────────────────────────────────────
        queue: deque[tuple[str, int]] = deque((u, 0) for u in all_seeds)

        async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
            while queue and len(state.pages) < state.max_pages:
                url, cur_depth = queue.popleft()
                if url in state.visited:
                    continue
                state.visited.add(url)

                # 合规检查: robots.txt
                allowed, reason = await check_robots_txt(url)
                if not allowed:
                    state.blocked += 1
                    state.blocked_urls.append(f"{url} ({reason})")
                    yield {
                        "phase": "fetch", "url": url, "status": "blocked",
                        "reason": reason, "page_num": len(state.pages),
                    }
                    continue

                # 请求间隔
                delay = get_crawl_delay(url)
                await asyncio.sleep(delay)

                page = await _fetch_and_extract(client, url, state.keyword, cur_depth, state)
                if page is None:
                    yield {
                        "phase": "fetch", "url": url, "status": "fail",
                        "page_num": len(state.pages),
                    }
                    continue

                is_relevant = page.keyword_count > 0
                if is_relevant:
                    state.relevant_count += 1
                state.pages.append(page)

                kb = 0  # 估算
                yield {
                    "phase": "fetch", "url": url, "title": page.title,
                    "status": "ok", "relevant": is_relevant,
                    "page_num": len(state.pages), "total": "?",
                    "depth": cur_depth, "kb": kb,
                }

                # 不够相关结果数 → 继续挖链接
                if state.relevant_count < state.min_relevant and cur_depth < state.depth:
                    sub_urls = _extract_link_urls(page.links_text)
                    for sub in sub_urls:
                        if len(queue) + len(state.pages) < state.max_pages + 30:
                            queue.append((sub, cur_depth + 1))

                # 提前终止
                if state.relevant_count >= state.min_relevant and len(state.pages) >= state.max_pages:
                    break

        # ── 第三步: 更新缓存 + 返回结果 ────────────────────────────────────
        if state.pages:
            # 把相关页面 URL 写入缓存，下次直接从这些站爬
            cached_urls = [p.url for p in state.pages if p.keyword_count > 0]
            if cached_urls:
                _update_cache(kw, cached_urls)

        if not state.pages:
            yield {"success": False, "data": "", "error": f"关键词 '{kw}' 未爬取到任何页面", "_done": True}
            return

        result = _format_output(state)
        yield {"success": True, "data": result, "error": "", "_done": True}


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

    # 累计网络统计
    state.total_bytes += len(resp.content)
    state.total_requests += 1
    state.total_time += resp.elapsed.total_seconds()

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


def _format_network_stats(state: CrawlState) -> str:
    """格式化网络流量统计"""
    if state.total_requests == 0:
        return "网络: 无请求"
    kb = state.total_bytes / 1024
    if kb >= 1024:
        size_str = f"{kb / 1024:.1f} MB"
    else:
        size_str = f"{kb:.0f} KB"
    rate = kb / state.total_time if state.total_time > 0 else 0
    return f"网络: {size_str}  ·  请求 {state.total_requests} 次  ·  耗时 {state.total_time:.1f}s  ({rate:.0f} KB/s)"


# ── 格式化输出 ────────────────────────────────────────────────────────

def _format_output(state: CrawlState) -> str:
    lines = [
        f"关键词: {state.keyword}",
        f"爬取页面数: {len(state.pages)}  相关页面数: {state.relevant_count}  被拦截: {state.blocked}",
        f"爬取深度: {state.depth}  上限: {state.max_pages}",
        _format_network_stats(state),
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
