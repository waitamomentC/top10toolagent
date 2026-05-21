from __future__ import annotations

from abc import ABC, abstractmethod


class BaseLLM(ABC):
    """LLM 抽象基类 —— 方便替换不同模型"""

    @abstractmethod
    async def chat(self, messages: list[dict]) -> str: ...


class OpenAILLM(BaseLLM):
    """OpenAI 兼容接口 —— 支持 OpenAI / 阿里百炼 / DeepSeek 等"""

    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        from openai import AsyncOpenAI

        self.model = model
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def chat(self, messages: list[dict]) -> str:
        resp = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.3,
            max_tokens=2048,
        )
        return resp.choices[0].message.content or ""
