# ReAct Agent

基于 **ReAct（Reasoning + Acting）范式** 的轻量级智能 Agent，四层架构清晰分层，FastAPI 启动。

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
| **网关层** | `gateway/handler.py` | 请求校验、路由分发、响应封装 |
| **路由层** | `router/react_router.py` | ReAct 循环引擎：解析 Thought/Action、调度工具、拼装 Observation |
| **工具层** | `tools/` | 工具基类 + 内置工具 + 注册表，可插拔扩展 |

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
# LLM 配置 —— 支持 OpenAI / 阿里百炼 / DeepSeek 等兼容接口
export LLM_API_KEY="sk-your-api-key"                # 必填
export LLM_BASE_URL="https://api.openai.com/v1"     # OpenAI 兼容 base_url
export LLM_MODEL="gpt-4o-mini"                       # 模型名称
```

**常用平台配置示例：**

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
# 健康检查
curl http://localhost:8000/health

# 执行 Agent
curl -X POST http://localhost:8000/agent/run \
  -H "Content-Type: application/json" \
  -d '{
    "query": "今天是几号？然后帮我算一下 123 * 456",
    "max_steps": 10
  }'
```

## API

### POST `/agent/run`

```json
// Request
{
  "query": "string",       // 用户问题
  "max_steps": 10,         // ReAct 最大循环步数 (1-50)
  "stream": false          // 流式输出 (预留)
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
      "observation": "2026-05-21 23:00:00"
    }
  ],
  "tool_calls": [
    {
      "tool_name": "datetime",
      "arguments": "now",
      "result": "2026-05-21 23:00:00"
    }
  ]
}
```

### GET `/health`

返回服务和可用工具列表。

## 路由层格式拦截

**Excel 工具限定规则**：仅支持 Microsoft Excel（`.xlsx` / `.xls`）格式。如果用户 query 中包含 `.csv` `.json` `.pdf` `.txt` 等非 Excel 文件扩展名，**网关层直接拦截返回错误，不进入 LLM**，节省 token 消耗。

```bash
# ❌ 被拦截 —— 直接返回错误，不调用 LLM
curl -X POST http://localhost:8000/agent/run \
  -H "Content-Type: application/json" \
  -d '{"query": "读取 data.csv 文件并计算总和"}'
# → {"answer": "不支持的文件格式: .csv。仅支持 Microsoft Excel (.xlsx / .xls) 文件操作。"}

# ✅ 放行
curl -X POST http://localhost:8000/agent/run \
  -H "Content-Type: application/json" \
  -d '{"query": "读取 sales.xlsx 文件并计算总和"}'
```

**拦截层级**（双重防护）：

1. **网关层**（`gateway/handler.py`）：扫描用户 query，命中非 Excel 扩展名 → 直接返回，不调用 LLM
2. **路由层**（`router/react_router.py`）：LLM 生成的 Action Input 中如果携带非 Excel 路径 → 返回格式化错误 Observation 给 LLM 自行修正

## 内置工具

| 工具 | 名称 | 说明 |
|------|------|------|
| CalculatorTool | `calculator` | 数学计算，支持 `+ - * / ** sqrt() sin()` 等 |
| DateTimeTool | `datetime` | 获取当前日期/时间 |
| WebSearchTool | `search` | 模拟搜索（生产环境替换为 SerpAPI / Tavily 等） |
| ReadExcelTool | `read_excel` | 读取本地 Excel 文件（仅 .xlsx / .xls） |
| WriteExcelTool | `write_excel` | 写入本地 Excel 文件（仅 .xlsx） |

## 添加自定义工具

```python
from tools.base import BaseTool
from models.schemas import ToolResult

class MyTool(BaseTool):
    name = "my_tool"
    description = "我的自定义工具 —— 输入 xxx，返回 yyy"

    async def execute(self, input_str: str) -> ToolResult:
        # 实现工具逻辑
        return ToolResult(success=True, data=f"处理结果: {input_str}")

# 在 main.py 中注册
registry.register(MyTool())
```

## 项目结构

```
agent/
├── main.py                  # 入口层: FastAPI + 依赖注入
├── requirements.txt
├── core/
│   └── llm.py               # LLM 抽象 + OpenAI 兼容客户端
├── gateway/
│   └── handler.py           # 网关层: 请求处理
├── router/
│   └── react_router.py      # 路由层: ReAct 循环引擎
├── tools/
│   ├── base.py              # 工具基类
│   ├── builtin.py           # 内置工具 (计算器/日期/搜索)
│   ├── excel.py             # Excel 工具 (读取/写入 + 格式校验)
│   └── registry.py          # 工具注册表
└── models/
    └── schemas.py           # Pydantic 数据模型
```
