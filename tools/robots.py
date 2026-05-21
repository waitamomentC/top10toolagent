"""爬虫合规检查: robots.txt / meta robots / X-Robots-Tag

严格遵循 Robots Exclusion Protocol (RFC 9309)。
网站不允许抓取 → 立刻停止，绝不强行破解。
"""

from __future__ import annotations

import asyncio
import re
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

# ── 常量 ──────────────────────────────────────────────────────────────

UA_FULL = "GeoAgent/1.0 (compatible; +https://github.com/geo-agent)"
CRAWL_DELAY = 3  # 默认爬取间隔（秒），如果 robots.txt 没有指定
ROBOTS_TIMEOUT = 10  # 获取 robots.txt 的超时

# ── 缓存 ──────────────────────────────────────────────────────────────

_robots_cache: dict[str, tuple[RobotFileParser | None, float]] = {}
# 值: (parser_or_None, fetch_time)
# None 表示该域名无 robots.txt / 获取失败 → 默认允许但需人工判断


async def check_robots_txt(url: str) -> tuple[bool, str]:
    """
    检查目标 URL 是否被 robots.txt 允许抓取。

    返回: (allowed: bool, reason: str)
      - (True, "") → 允许
      - (False, "原因") → 禁止
    """
    parsed = urlparse(url)
    domain = f"{parsed.scheme}://{parsed.netloc}"

    # 检查缓存
    if domain in _robots_cache:
        rp, _ = _robots_cache[domain]
    else:
        rp = await _fetch_robots_txt(domain)
        _robots_cache[domain] = (rp, asyncio.get_event_loop().time())

    if rp is None:
        # 无 robots.txt → 默认视为允许，但保守处理
        return True, ""

    allowed = rp.can_fetch(UA_FULL, url)
    if allowed:
        delay = rp.crawl_delay(UA_FULL) or CRAWL_DELAY
        return True, ""
    else:
        return False, f"robots.txt 禁止抓取: {url}"


def check_meta_robots(soup: BeautifulSoup) -> tuple[bool, str]:
    """
    检查 HTML 中 <meta name="robots"> 是否禁止索引/抓取。

    返回: (allowed: bool, reason: str)
    """
    for meta in soup.find_all("meta", attrs={"name": re.compile(r"^robots$", re.I)}):
        content = meta.get("content", "").lower()
        directives = {d.strip() for d in content.split(",")}
        if "noindex" in directives:
            return False, "页面 meta robots 标记 noindex（禁止索引）"
        if "nofollow" in directives:
            # nofollow 只是不跟踪链接，仍然可以抓取当前页
            pass
        if "none" in directives:
            return False, "页面 meta robots 标记 none（完全禁止）"
    return True, ""


def check_robots_header(headers: httpx.Headers) -> tuple[bool, str]:
    """
    检查 HTTP 响应头 X-Robots-Tag 是否禁止抓取。

    返回: (allowed: bool, reason: str)
    """
    robot_tag = headers.get("X-Robots-Tag", "")
    if not robot_tag:
        return True, ""
    directives = {d.strip().lower() for d in robot_tag.split(",")}
    if "noindex" in directives:
        return False, "HTTP X-Robots-Tag 标记 noindex（禁止索引）"
    if "none" in directives:
        return False, "HTTP X-Robots-Tag 标记 none（完全禁止）"
    return True, ""


def get_crawl_delay(url: str) -> float:
    """获取指定域名的爬取延迟（秒）"""
    parsed = urlparse(url)
    domain = f"{parsed.scheme}://{parsed.netloc}"
    entry = _robots_cache.get(domain)
    if entry and entry[0] is not None:
        delay = entry[0].crawl_delay(UA_FULL)
        if delay is not None:
            return float(delay)
    return CRAWL_DELAY


# ── 内部 ──────────────────────────────────────────────────────────────

async def _fetch_robots_txt(domain: str) -> RobotFileParser | None:
    """获取并解析 robots.txt"""
    robots_url = f"{domain}/robots.txt"
    try:
        async with httpx.AsyncClient(timeout=ROBOTS_TIMEOUT, follow_redirects=True) as client:
            resp = await client.get(robots_url)
            if resp.status_code == 404:
                return None  # 无 robots.txt，视为允许
            resp.raise_for_status()
    except Exception:
        return None  # 获取失败，默认谨慎允许

    rp = RobotFileParser()
    rp.set_url(robots_url)
    try:
        rp.parse(resp.text.splitlines())
    except Exception:
        return None
    return rp
