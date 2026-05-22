"""步骤: ①获取具体日期 → ②用具体日期关键词爬取 → ③直接抓取已发现的热榜页"""
import asyncio
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from tools.builtin import DateTimeTool
from tools.web_scraper import WebScraperTool
from tools.web_crawler import WebCrawlerTool


async def main():
    # ① 确认具体日期 —— "当日"必须解析为精确日期
    dt = DateTimeTool()
    r = await dt.execute("now")
    now_str = r.data
    # 提取日期部分: "2026-05-21"
    date_part = now_str.split(" ")[0]
    date_cn = f"{date_part[:4]}年{int(date_part[5:7])}月{int(date_part[8:10])}日"
    print(f"[时间确认] 当前时间: {now_str}")
    print(f"[日期解析] 当日 = {date_cn}")
    print()

    # ② 用具体日期构建关键词爬取
    keyword = f"抖音热榜 {date_cn}"
    print(f"[爬取关键词] '{keyword}'")
    print("=" * 60)
    crawler = WebCrawlerTool()
    result = await crawler.execute(
        '{"keyword":"' + keyword + '", "depth":1, "max_pages":30, "min_relevant":10}'
    )
    if result.success:
        print(result.data[:8000])
    else:
        print(f"爬取失败: {result.error}")

    # ③ 直接抓取 abangshou.com 热榜页（上轮已发现该站有数据）
    print()
    print("=" * 60)
    print("[补充抓取] abangshou.com 完整热榜内容")
    scraper = WebScraperTool()
    r2 = await scraper.execute("https://www.abangshou.com/tools/douyin.html")
    if r2.success:
        print(r2.data[:5000])
    else:
        print(f"抓取失败: {r2.error}")

if __name__ == "__main__":
    asyncio.run(main())
