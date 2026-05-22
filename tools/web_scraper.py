from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from models.schemas import ToolResult
from tools.base import BaseTool
from tools.robots import check_meta_robots, check_robots_header, check_robots_txt

# ── 常量 ──────────────────────────────────────────────────────────────

MAX_CONTENT_LEN = 200     # 正文截断至摘要级别（版权安全）
MAX_LINKS = 50            # 最多提取链接数
TIMEOUT = 15              # 请求超时 (秒)
UA = "GeoAgent/1.0 (compatible; +https://github.com/waitamomentC/top10toolagent)"

# 发布时间相关的 meta / 属性名
TIME_SELECTORS = [
    'meta[property="article:published_time"]',
    'meta[property="article:modified_time"]',
    'meta[name="date"]',
    'meta[name="DC.date"]',
    'meta[name="pubdate"]',
    'meta[name="publish_date"]',
    'meta[name="weibo:article:create_at"]',
    'meta[itemprop="datePublished"]',
    'meta[itemprop="dateModified"]',
    'meta[property="og:updated_time"]',
    'meta[property="og:pubdate"]',
    'time[datetime]',
    'time[pubdate]',
]

# 需要移除的干扰标签
STRIP_TAGS = [
    "script", "style", "nav", "footer", "header",
    "aside", "noscript", "iframe", "form",
    "select", "button", "svg",
]


# ── 工具实现 ──────────────────────────────────────────────────────────

class WebScraperTool(BaseTool):
    name = "web_scraper"
    description = (
        "抓取指定网页内容，提取发布时间、页面链接、正文。"
        "输入为完整 URL（如 https://example.com/article），返回结构化信息。"
    )

    async def execute(self, input_str: str) -> ToolResult:
        url = input_str.strip()

        # 校验 URL
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return ToolResult(
                success=False, data="",
                error=f"仅支持 http/https 协议，收到: {parsed.scheme}",
            )
        if not parsed.netloc:
            return ToolResult(success=False, data="", error="URL 缺少域名")

        # ── 合规检查 ①: robots.txt ────────────────────────────────────
        allowed, reason = await check_robots_txt(url)
        if not allowed:
            return ToolResult(success=False, data="", error=f"抓取被拒绝: {reason}")

        # 发起请求
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
                resp = await client.get(
                    url,
                    headers={"User-Agent": UA, "Accept": "text/html"},
                )
                resp.raise_for_status()
                html = resp.text
                final_url = str(resp.url)
                resp_headers = resp.headers
        except httpx.TimeoutException:
            return ToolResult(success=False, data="", error=f"请求超时 ({TIMEOUT}s): {url}")
        except httpx.HTTPStatusError as e:
            return ToolResult(success=False, data="", error=f"HTTP {e.response.status_code}: {url}")
        except Exception as e:
            return ToolResult(success=False, data="", error=str(e))

        # 流量统计
        download_kb = len(resp.content) / 1024
        elapsed = resp.elapsed.total_seconds()

        soup = BeautifulSoup(html, "lxml")

        # ── 合规检查 ②: meta robots ───────────────────────────────────
        allowed, reason = check_meta_robots(soup)
        if not allowed:
            return ToolResult(success=False, data="", error=f"抓取被拒绝: {reason}")

        # ── 合规检查 ③: X-Robots-Tag ──────────────────────────────────
        allowed, reason = check_robots_header(resp_headers)
        if not allowed:
            return ToolResult(success=False, data="", error=f"抓取被拒绝: {reason}")

        # 提取三项信息
        publish_time = _extract_time(soup)
        links = _extract_links(soup, final_url)
        content = _extract_content(soup)

        result_parts = [
            f"URL: {final_url}",
            f"标题: {_extract_title(soup)}",
            f"发布时间: {publish_time}",
            f"网络: {download_kb:.1f} KB  ·  耗时 {elapsed:.2f}s  ({download_kb / elapsed:.0f} KB/s)" if elapsed > 0 else f"网络: {download_kb:.1f} KB",
            "",
            "--- 链接 ---",
            links or "(无链接)",
            "",
            "--- 正文 ---",
            content or "(未能提取正文)",
        ]
        return ToolResult(success=True, data="\n".join(result_parts))


# ── 提取函数 ──────────────────────────────────────────────────────────

def _extract_title(soup: BeautifulSoup) -> str:
    if soup.title:
        return soup.title.get_text(strip=True)
    h1 = soup.find("h1")
    return h1.get_text(strip=True) if h1 else "(无标题)"


def _extract_time(soup: BeautifulSoup) -> str:
    for selector in TIME_SELECTORS:
        tag = soup.select_one(selector)
        if not tag:
            continue
        # <meta content="...">
        val = tag.get("content") or tag.get("datetime") or tag.get("pubdate")
        if val:
            return _normalize_time(val)
    return "(未找到发布时间)"


def _extract_links(soup: BeautifulSoup, base_url: str) -> str:
    seen: set[str] = set()
    lines: list[str] = []
    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        if not href or href.startswith("#") or href.startswith("javascript:"):
            continue
        full = urljoin(base_url, href)
        if full in seen:
            continue
        seen.add(full)
        text = a.get_text(strip=True) or "(无文本)"
        lines.append(f"  [{text}] → {full}")
        if len(lines) >= MAX_LINKS:
            lines.append(f"  ... (超出 {MAX_LINKS} 条，已截断)")
            break
    return "\n".join(lines) if lines else ""


def _extract_content(soup: BeautifulSoup) -> str:
    # 优先 <article> → <main> → <body>
    container = soup.find("article") or soup.find("main") or soup.body
    if not container:
        return ""

    # 移除干扰标签 (script / style / nav / footer / header ...)
    for tag_name in STRIP_TAGS:
        for t in container.find_all(tag_name):
            t.decompose()

    text = container.get_text(separator="\n", strip=True)
    # 合并多余空行
    text = re.sub(r"\n{3,}", "\n\n", text)
    if len(text) > MAX_CONTENT_LEN:
        text = text[:MAX_CONTENT_LEN] + f"\n...(截断，共 {len(text)} 字符)"
    return text


def _normalize_time(raw: str) -> str:
    """尝试归一化为 ISO 格式"""
    raw = raw.strip()
    for fmt in [
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d",
        "%d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
    ]:
        try:
            dt = datetime.strptime(raw, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.strftime("%Y-%m-%d %H:%M:%S %Z")
        except ValueError:
            continue
    return raw[:50]
