# top10tool — 热搜 TOP10 智能工具

基于 **ReAct（Reasoning + Acting）范式** 的轻量级智能 Agent。终端聊天式交互界面，类 ChatGPT/Claude 对话体验。

---

## 全局安装

一处安装，全局可用。

### 1. 下载 & 安装

```bash
git clone https://github.com/waitamomentC/top10toolagent.git
pip install ./top10toolagent
```

安装后自动创建 `top10tool` 命令（Python Scripts 目录，天然在系统 PATH 中）。

> 如果 pip 提示 `command not found`，换用 `python3 -m pip install ./top10toolagent`。

### 2. 启动

在**任意终端**输入：

```bash
top10tool
```

首次运行会引导配置 LLM 连接信息（API 地址、Key、模型）。配置一次即可，之后直接进入聊天界面。

### 3. 聊天命令

| 输入 | 说明 |
|------|------|
| `当日XXX热搜` | 爬取指定平台热搜（如 `当日抖音热搜`、`当日微博热搜`） |
| `/config` | 查看当前 LLM 配置 |
| `/uninstall` | 显示卸载方法 |
| `/exit` `/quit` `/q` | 退出 |

### 4. 卸载

```bash
pip uninstall top10tool -y
```

配置文件在 `~/.top10tool/`，自行删除即可。

---

## 架构

```
请求 → 入口层 (main.py) → 网关层 (gateway/) → 路由层 (router/) → 工具层 (tools/)
                                                     │
                                                     ▼
                                             ReAct 循环引擎
                                        Thought → Action → Observation
```

| 层级 | 目录 | 职责 |
|------|------|------|
| **入口层** | `main.py` | FastAPI 应用、依赖注入、生命周期管理 |
| **网关层** | `gateway/handler.py` | 请求校验（热搜格式 + Excel 格式）、路由分发、响应封装 |
| **路由层** | `router/react_router.py` | ReAct 循环引擎：解析 Thought/Action、调度工具、拼装 Observation |
| **工具层** | `tools/` | 工具基类 + 内置工具 + 注册表，可插拔扩展 |

---

## FastAPI 服务模式

如需要通过 HTTP API 调用 Agent：

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

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

### 3. 启动服务

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. 测试

```bash
curl http://localhost:8000/health

curl -X POST http://localhost:8000/agent/run \
  -H "Content-Type: application/json" \
  -d '{"query": "今天是几号？然后帮我算一下 123 * 456", "max_steps": 10}'
```

## API

### POST `/agent/run`

```json
// Request
{
  "query": "string",
  "max_steps": 10,
  "stream": false
}

// Response
{
  "answer": "计算结果为 56088。",
  "steps": [
    {
      "step": 1,
      "thought": "需要先获取当前日期",
      "action": "datetime",
      "action_input": "now",
      "observation": "2026-05-22 23:00:00"
    }
  ],
  "tool_calls": [
    { "tool_name": "datetime", "arguments": "now", "result": "2026-05-22 23:00:00" }
  ]
}
```

### GET `/health`

返回服务状态和可用工具列表。

## 格式拦截

**双重防护**，避免无效请求消耗 LLM token。

### 热搜格式

用户输入必须符合 `当日XXX热搜` 格式：

```bash
# 被拦截
curl ... -d '{"query": "当日AI热搜"}'
# → 输入格式错误，请使用「当日XXX热搜」格式
```

### Excel 格式

仅支持 `.xlsx` / `.xls`：

```bash
# 被拦截，零 token 消耗
curl ... -d '{"query": "读取 data.csv"}'
# → 不支持的文件格式: .csv

# 放行
curl ... -d '{"query": "读取 sales.xlsx"}'
```

**拦截层级**：

1. **网关层** `gateway/handler.py`：扫描 query → 命中非法格式直接返回
2. **路由层** `router/react_router.py`：LLM 生成的输入再校验一次

## 内置工具

| 工具 | 名称 | 说明 |
|------|------|------|
| CalculatorTool | `calculator` | 数学计算 |
| DateTimeTool | `datetime` | 获取当前日期/时间 |
| WebSearchTool | `search` | 模拟搜索 |
| ReadExcelTool | `read_excel` | 读取 Excel（仅 .xlsx/.xls） |
| WriteExcelTool | `write_excel` | 写入 Excel（仅 .xlsx） |
| WebScraperTool | `web_scraper` | 单页抓取 |
| WebCrawlerTool | `web_crawler` | 全网 BFS 关键词爬虫 |
| ListExcelFilesTool | `list_excel_files` | 列出项目根目录 Excel 文件 |

## 添加自定义工具

```python
from tools.base import BaseTool
from models.schemas import ToolResult

class MyTool(BaseTool):
    name = "my_tool"
    description = "我的自定义工具"

    async def execute(self, input_str: str) -> ToolResult:
        return ToolResult(success=True, data=f"处理: {input_str}")

registry.register(MyTool())
```

## 项目结构

```
top10toolagent/
├── cli.py                    # 终端 CLI 入口
├── main.py                   # FastAPI 入口
├── pyproject.toml            # pip 包定义
├── setup.bat / setup.sh      # 一键安装脚本
├── uninstall.bat / uninstall.sh  # 卸载脚本
├── run_crawl.py              # 独立爬虫脚本
├── test_react.py             # ReAct 测试
├── test_workflow.py          # 工作流测试
├── requirements.txt
├── core/
│   └── llm.py                # LLM 抽象 + OpenAI 兼容客户端
├── gateway/
│   └── handler.py            # 请求校验 + 路由分发
├── router/
│   └── react_router.py       # ReAct 循环引擎
├── tools/
│   ├── base.py               # 工具基类
│   ├── builtin.py            # 内置工具
│   ├── excel.py              # Excel 工具
│   ├── file_utils.py         # 文件管理
│   ├── registry.py           # 工具注册表
│   ├── robots.py             # robots.txt 合规检查
│   ├── web_scraper.py        # 单页抓取
│   └── web_crawler.py        # 关键词爬虫
└── models/
    └── schemas.py            # Pydantic 数据模型
```

## 法律声明

本工具**仅供个人学习研究和技术交流**，禁止商用。

- 爬虫严格遵守 RFC 9309 (robots.txt)，不破解、不伪装浏览器 UA
- 每次请求间隔 ≥3 秒，正文仅抓取 200 字摘要级别
- 使用者须自行确保符合所在国家/地区法律
- 作者不对使用本工具产生的任何法律后果承担责任
- 详细见 [LICENSE](LICENSE)
