# top10tool — 热搜 TOP10 智能工具

基于 **ReAct（Reasoning + Acting）范式** 的轻量级智能 Agent。终端聊天式交互界面，类 Claude Code 风格。

---

## 全局安装

一处安装，全局可用。

### 1. 下载 & 安装

```bash
git clone https://github.com/waitamomentC/top10toolagent.git
pip install ./top10toolagent
```

安装后自动创建 `top10tool` 命令，任意终端可用。

> 如果 pip 提示 `command not found`，换用 `python3 -m pip install ./top10toolagent`。

### 2. 启动

```bash
top10tool
```

首次运行引导配置 LLM（API 地址、Key、模型）。配置一次即可。

启动时自动检查更新：
```
  检查更新...
  ⚡ 发现新版本 (2 个提交):
    05aa4d6 fix: 自动更新改为对比已安装版本
    1b76bd0 feat: URL缓存升级
  是否更新? [Y/n]
```

确认后自动 `git pull` + `pip reinstall`，重启即生效。

### 3. 聊天命令

| 输入 | 说明 |
|------|------|
| `当日抖音热搜` | ReAct 流程：LLM 调爬虫 → 流式爬取 → LLM 验证 → 写 Excel |
| `当日微博热搜` | 同上，平台自动识别 |
| `/config` | 查看当前 LLM 配置 |
| `/modify` | 修改 LLM 配置（纯本地，不走 LLM） |
| `/exit` `/quit` `/q` | 退出 |
| `/uninstall` | 显示卸载方法 |

### 4. 卸载

```bash
pip uninstall top10tool -y
rm -rf ~/.top10tool
```

---

## 工作流

```
用户: 当日抖音热搜
  │
  ● [1] LLM 思考 → datetime（获取日期）
  ● [2] LLM 思考 → web_crawler("抖音热榜 YYYY年M月D日")
  │
  │  LLM 休眠 ──┐ 爬虫流式执行：
  │             │  🔍 搜索 → ✓ 页面1 ✓ 页面2 ⊘ 不符合条件 ...
  │  LLM 唤醒 ←─┘
  │
  ● [3] LLM 验证: 日期是否今天？热度 ≥800万？≥10条？
  │       ↓ 不合格 → 调整参数重爬
  │       ↓ 合格   → 继续
  ● [4] list_excel_files → 确认文件
  ● [5] write_excel → 写入
  ● [6] ✅ 已写入 15 条到 ../douyin_trending.xlsx
```

**关键设计：** LLM 调用爬虫后立即休眠，爬虫流式跑完再唤醒。LLM 不阻塞、不超时、不空转。

---

## 爬虫特性

### 流式进度反馈

每爬一个页面实时显示：URL、标题、是否命中、被拦截/不符合条件、网络流量。

```
  🔍 缓存命中 5 个站点，优先爬取
  🔍 共获取 35 个种子页面（缓存 5 + 搜索 30）
  ✓ [1] ★ 抖音热榜 - 实时热搜 (douyin.com/...)
  ✓ [2] ★ xxx新闻网 - 热搜榜 (xxx.com/...)
  ⊘ [3] 不符合条件: yyy.com/...
  网络: 2.3 MB  ·  请求 25 次  ·  耗时 12.3s  (188 KB/s)
```

### URL 缓存库

`~/.top10tool/cache/` 下按平台生成 `.md` 缓存文件：

```markdown
# 抖音 爬虫URL缓存
> 最后更新: 2026-05-23T10:30+00:00

| URL | 最后抓取 | 成功率 | 命中/抓取 |
|-----|----------|--------|----------|
| https://douyin.com/hot | 2026-05-23 | 100% | 3/3 |
| https://news.qq.com/trending | 2026-05-22 | 50%  | 1/2 |
```

- 按成功率从高到低优先爬取
- 有效 URL 记录成功次数，无效 URL 不录入
- 7 天未更新淘汰，30 天无活动清理

### 数据验证

爬取结果交给 LLM 逐条验证：
- 日期是否为当日
- 热度是否 ≥800 万
- 合格数量是否 ≥10 条
- 来源是否可信

不合格自动重爬（调大参数或调整关键词）。

---

## 架构

```
CLI (cli.py) → ReAct 循环 (router/) → 工具层 (tools/)
                    │                      │
                    ▼                      ▼
            LLM 思考/决策          爬虫/Excel/计算器...
          (每次独立HTTP请求)
```

| 层级 | 目录 | 职责 |
|------|------|------|
| **终端层** | `cli.py` | 交互界面、更新检测、问候拦截、`/modify` |
| **路由层** | `router/react_router.py` | ReAct 循环引擎、流式工具调度 |
| **工具层** | `tools/` | 爬虫、Excel、计算器等可插拔工具 |
| **模型层** | `models/schemas.py` | Pydantic 数据模型 |

---

## FastAPI 服务模式

### 配置环境变量

```bash
export LLM_API_KEY="sk-your-api-key"
export LLM_BASE_URL="https://api.openai.com/v1"
export LLM_MODEL="gpt-4o-mini"
```

| 平台 | LLM_BASE_URL | LLM_MODEL 示例 |
|------|-------------|---------------|
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` / `gpt-4o` |
| 阿里百炼 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` / `qwen-max` |
| DeepSeek | `https://api.deepseek.com` | `deepseek-chat` |
| Ollama 本地 | `http://localhost:11434/v1` | `llama3` |

### 启动服务

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### API

```bash
# 健康检查
curl http://localhost:8000/health

# 执行 Agent
curl -X POST http://localhost:8000/agent/run \
  -H "Content-Type: application/json" \
  -d '{"query": "今天是几号？123 * 456", "max_steps": 10}'
```

---

## 内置工具

| 工具 | 名称 | 说明 |
|------|------|------|
| CalculatorTool | `calculator` | 数学计算 |
| DateTimeTool | `datetime` | 获取当前日期/时间 |
| WebCrawlerTool | `web_crawler` | 全网关键词爬虫（BFS + 流式进度 + 缓存） |
| WebScraperTool | `web_scraper` | 单页抓取 + 网络统计 |
| ReadExcelTool | `read_excel` | 读取 Excel（.xlsx/.xls） |
| WriteExcelTool | `write_excel` | 写入 Excel（.xlsx） |
| ListExcelFilesTool | `list_excel_files` | 列出项目根目录 Excel 文件 |

---

## 项目结构

```
top10toolagent/
├── cli.py                    # 终端 CLI（更新检测 + ReAct 流式界面）
├── main.py                   # FastAPI 入口
├── pyproject.toml            # pip 包定义
├── setup.bat / setup.sh      # 一键安装（含版本追踪）
├── uninstall.bat / uninstall.sh
├── core/
│   └── llm.py                # LLM 抽象 + OpenAI 兼容客户端
├── gateway/
│   └── handler.py            # 请求校验 + 路由分发
├── router/
│   └── react_router.py       # ReAct 循环引擎 + 流式工具调度
├── tools/
│   ├── base.py               # 工具基类
│   ├── builtin.py            # 内置工具（计算器/日期/搜索）
│   ├── excel.py              # Excel 读写
│   ├── file_utils.py         # 文件管理
│   ├── registry.py           # 工具注册表
│   ├── robots.py             # robots.txt 合规检查
│   ├── web_scraper.py        # 单页抓取 + 网络流量统计
│   └── web_crawler.py        # 关键词爬虫 + 流式进度 + MD缓存
└── models/
    └── schemas.py            # Pydantic 数据模型
```

---

## 法律声明

本工具**仅供个人学习研究和技术交流**，禁止商用。

- 爬虫遵守 RFC 9309 (robots.txt)，不破解、不伪装浏览器 UA
- 每次请求间隔遵守 Crawl-Delay 指令
- 正文仅抓取 200 字摘要级别
- 使用者须自行确保符合所在国家/地区法律
- 作者不对使用本工具产生的任何法律后果承担责任
- 详细见 [LICENSE](LICENSE)
