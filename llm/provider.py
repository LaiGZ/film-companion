"""
LLM 提供者抽象层 — 统一接口，支持切换模型
"""

import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import yaml


# ============================================================
# 配置加载
# ============================================================

@dataclass
class LLMConfig:
    provider: str = "openai"
    model: str = "gpt-4o"
    temperature: float = 0.3
    max_tokens: int = 2000
    api_key: str = ""
    base_url: str = ""


def load_config() -> LLMConfig:
    """加载 LLM 配置"""
    config_path = os.path.join(os.path.dirname(__file__), "..", "config", "config.yaml")

    cfg = LLMConfig()

    if os.path.exists(config_path):
        with open(config_path) as f:
            data = yaml.safe_load(f)
        llm_cfg = data.get("llm", {})
        cfg.provider = llm_cfg.get("provider", "openai")
        cfg.model = llm_cfg.get("model", "gpt-4o")
        cfg.temperature = llm_cfg.get("temperature", 0.3)
        cfg.max_tokens = llm_cfg.get("max_tokens", 2000)
        cfg.base_url = llm_cfg.get("base_url", "")
        cfg.api_key = llm_cfg.get("api_key", "")

    # 环境变量覆盖
    cfg.provider = os.getenv("LLM_PROVIDER", cfg.provider)
    cfg.model = os.getenv("LLM_MODEL", cfg.model)

    # API Key — 环境变量覆盖 config.yaml，但只在环境变量实际存在时才覆盖
    api_key_env_name = f"{cfg.provider.upper()}_API_KEY"
    env_api_key = os.getenv(api_key_env_name)
    if env_api_key:
        cfg.api_key = env_api_key
    elif not cfg.api_key:
        cfg.api_key = os.getenv("OPENAI_API_KEY", "")

    return cfg


# ============================================================
# 统一响应模型
# ============================================================

@dataclass
class LLMResponse:
    content: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    finish_reason: str = ""


# ============================================================
# 抽象基类
# ============================================================

class LLMProvider(ABC):
    """所有 LLM 提供者的统一接口"""

    def __init__(self, config: LLMConfig):
        self.config = config

    @abstractmethod
    async def chat(self, messages: list, tools: list = None,
                   system_prompt: str = None) -> LLMResponse:
        """调用 LLM，返回结构化响应"""
        ...

    async def chat_stream(self, messages: list, tools: list = None,
                          system_prompt: str = None):
        """流式调用 LLM，逐 token 产出

        Yields dict: {"type": "token", "content": str}
                     {"type": "done", "content": str, "tool_calls": list}
                     {"type": "error", "content": str}

        默认实现退化为非流式单次输出（子类应重写以获得真实流式效果）
        """
        resp = await self.chat(messages, tools, system_prompt)
        yield {"type": "token", "content": resp.content}
        yield {"type": "done", "content": resp.content,
               "tool_calls": resp.tool_calls}

    def _format_messages(self, messages: list, system_prompt: str = None) -> list:
        """将内部消息格式转为标准格式"""
        formatted = []
        if system_prompt:
            formatted.append({"role": "system", "content": system_prompt})
        formatted.extend(messages)
        return formatted


# ============================================================
# OpenAI 实现
# ============================================================

class OpenAIProvider(LLMProvider):
    """OpenAI API 调用"""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(api_key=config.api_key)

    async def chat(self, messages: list, tools: list = None,
                   system_prompt: str = None) -> LLMResponse:
        msgs = self._format_messages(messages, system_prompt)

        kwargs = {
            "model": self.config.model,
            "messages": msgs,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        resp = await self.client.chat.completions.create(**kwargs)
        msg = resp.choices[0].message

        tool_calls = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                tool_calls.append({
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    }
                })

        return LLMResponse(
            content=msg.content or "",
            tool_calls=tool_calls,
            usage={
                "prompt_tokens": resp.usage.prompt_tokens if resp.usage else 0,
                "completion_tokens": resp.usage.completion_tokens if resp.usage else 0,
            },
            finish_reason=msg.content or resp.choices[0].finish_reason or "",
        )


# ============================================================
# Claude 实现
# ============================================================

class ClaudeProvider(LLMProvider):
    """Anthropic Claude API 调用"""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        from anthropic import AsyncAnthropic
        self.client = AsyncAnthropic(api_key=config.api_key)

    def _to_claude_tools(self, tools: list) -> list | None:
        """将 OpenAI 格式的 tools 转为 Claude 格式"""
        if not tools:
            return None
        claude_tools = []
        for t in tools:
            if t.get("type") == "function":
                fn = t["function"]
                # Claude 需要不同的参数格式
                claude_tools.append({
                    "name": fn["name"],
                    "description": fn.get("description", ""),
                    "input_schema": fn.get("parameters", {}),
                })
        return claude_tools if claude_tools else None

    async def chat(self, messages: list, tools: list = None,
                   system_prompt: str = None) -> LLMResponse:
        # Claude 的 system 是独立参数
        claude_messages = []
        for m in messages:
            if m["role"] == "system":
                continue  # Claude 系统提示独立传
            role = "assistant" if m["role"] == "assistant" else m["role"]
            claude_messages.append({"role": role, "content": m["content"]})

        claude_tools = self._to_claude_tools(tools)

        kwargs = {
            "model": self.config.model,
            "messages": claude_messages,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        if claude_tools:
            kwargs["tools"] = claude_tools

        resp = await self.client.messages.create(**kwargs)

        content = ""
        tool_calls = []

        for block in resp.content:
            if block.type == "text":
                content += block.text
            elif block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "type": "function",
                    "function": {
                        "name": block.name,
                        "arguments": json.dumps(block.input),
                    }
                })

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            usage={
                "prompt_tokens": resp.usage.input_tokens if resp.usage else 0,
                "completion_tokens": resp.usage.output_tokens if resp.usage else 0,
            },
            finish_reason=resp.stop_reason or "",
        )


# ============================================================
# DeepSeek 实现（OpenAI 兼容接口）
# ============================================================

class DeepSeekProvider(LLMProvider):
    """DeepSeek API — 直接 HTTP 调用，避免 OpenAI SDK 兼容性问题"""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        import httpx
        self._http = httpx.AsyncClient(timeout=60)
        self.base_url = config.base_url or "https://api.deepseek.com"
        self.api_key = config.api_key

    async def chat(self, messages: list, tools: list = None,
                   system_prompt: str = None) -> LLMResponse:
        msgs = self._format_messages(messages, system_prompt)

        # 清理消息：移除 tool_calls 里的 reasoning_content
        cleaned_msgs = []
        for m in msgs:
            m = dict(m)  # 不修改原始消息
            role = m.get("role", "")
            # 如果 assistant 消息有 tool_calls 且 content 为空，DeepSeek 要求 content 不能是空字符串
            if role == "assistant" and m.get("content") == "":
                if m.get("tool_calls"):
                    m["content"] = None  # DeepSeek 接受 None，不接受 ""
            cleaned_msgs.append(m)

        # 构建请求体
        body = {
            "model": self.config.model,
            "messages": cleaned_msgs,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        if tools:
            # DeepSeek 使用标准的 OpenAI tool format
            body["tools"] = tools
            body["tool_choice"] = "auto"

        # 发送请求
        resp = await self._http.post(
            f"{self.base_url}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=body,
        )

        if resp.status_code != 200:
            err = resp.json()
            # 如果报 reasoning_content 错误，需要把 assistant 消息里补上 reasoning_content
            if "reasoning_content" in str(err):
                return await self._retry_with_reasoning(cleaned_msgs, tools, resp.json())

            raise Exception(f"DeepSeek API error {resp.status_code}: {err}")

        data = resp.json()
        choice = data["choices"][0]
        msg = choice["message"]
        usage = data.get("usage", {})

        # 解析 tool_calls
        tool_calls = []
        for tc in (msg.get("tool_calls") or []):
            tool_calls.append({
                "id": tc["id"],
                "type": "function",
                "function": {
                    "name": tc["function"]["name"],
                    "arguments": tc["function"]["arguments"],
                }
            })

        # 如果返回了 reasoning_content，存下来以便后续回传
        reasoning = msg.get("reasoning_content")
        if reasoning:
            # 标记这条消息有 reasoning_content，后续请求需包含
            pass  # 暂时忽略，等 _retry_with_reasoning 处理

        return LLMResponse(
            content=msg.get("content") or "",
            tool_calls=tool_calls,
            usage={
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
            },
            finish_reason=choice.get("finish_reason", ""),
        )

    async def chat_stream(self, messages: list, tools: list = None,
                          system_prompt: str = None):
        """DeepSeek 流式调用 — 逐 token 产出，含 reasoning_content 重试"""
        msgs = self._format_messages(messages, system_prompt)

        # 清理消息中的 reasoning_content 问题
        cleaned_msgs = []
        for m in msgs:
            m = dict(m)
            if m.get("role") == "assistant" and m.get("content") == "":
                if m.get("tool_calls"):
                    m["content"] = None
            cleaned_msgs.append(m)

        # 首次尝试 + 最多一次重试
        for attempt in range(2):
            body = {
                "model": self.config.model,
                "messages": cleaned_msgs,
                "temperature": self.config.temperature,
                "max_tokens": self.config.max_tokens,
                "stream": True,
            }
            if tools:
                body["tools"] = tools
                body["tool_choice"] = "auto"

            accumulated_text = ""
            accumulated_tool_calls: dict[int, dict] = {}
            has_reasoning_error = False

            async with self._http.stream(
                "POST",
                f"{self.base_url}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
            ) as resp:
                if resp.status_code != 200:
                    err_body = await resp.aread()
                    err_text = err_body.decode()
                    # 如果报 reasoning_content 错误且还有重试机会
                    if attempt == 0 and "reasoning_content" in err_text:
                        has_reasoning_error = True
                        # 修复消息：给所有带 tool_calls 的 assistant 消息补上 reasoning_content
                        cleaned_msgs = []
                        for m in (self._format_messages(messages, system_prompt) if attempt == 0 else cleaned_msgs):
                            m = dict(m)
                            if m.get("role") == "assistant" and m.get("tool_calls"):
                                m["reasoning_content"] = ""
                            if m.get("role") == "assistant" and m.get("content") == "":
                                if m.get("tool_calls"):
                                    m["content"] = None
                            cleaned_msgs.append(m)
                        continue  # 重试

                    yield {"type": "error", "content": f"API Error {resp.status_code}: {err_text[:200]}"}
                    return

                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:].strip()
                    if payload == "[DONE]":
                        break
                    try:
                        chunk = json.loads(payload)
                    except json.JSONDecodeError:
                        continue

                    choices = chunk.get("choices", [])
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {})
                    finish_reason = choices[0].get("finish_reason")

                    # 内容 token
                    content = delta.get("content")
                    if content:
                        accumulated_text += content
                        yield {"type": "token", "content": content}

                    # 工具调用 delta
                    tc_delta = delta.get("tool_calls")
                    if tc_delta:
                        for tc in tc_delta:
                            idx = tc.get("index", 0)
                            if idx not in accumulated_tool_calls:
                                accumulated_tool_calls[idx] = {
                                    "id": tc.get("id", f"call_{idx}"),
                                    "type": "function",
                                    "function": {"name": "", "arguments": ""},
                                }
                            fn = tc.get("function", {})
                            if fn.get("name"):
                                accumulated_tool_calls[idx]["function"]["name"] += fn["name"]
                            if fn.get("arguments"):
                                accumulated_tool_calls[idx]["function"]["arguments"] += fn["arguments"]

            # 如果没有报错，正常结束
            if not has_reasoning_error:
                break

        # 流式结束
        tool_calls = [v for _, v in sorted(accumulated_tool_calls.items())] if accumulated_tool_calls else []
        yield {"type": "done", "content": accumulated_text, "tool_calls": tool_calls}

    async def _retry_with_reasoning(self, messages: list, tools: list,
                                    original_error: dict) -> LLMResponse:
        """当报 reasoning_content 错误时，找出缺少该字段的 assistant 消息并补上"""
        # 重试策略：找到最近一条 assistant 消息，补上空的 reasoning_content
        fixed_msgs = []
        for m in messages:
            m = dict(m)
            if m.get("role") == "assistant" and m.get("tool_calls"):
                # 补上 reasoning_content 字段
                m.setdefault("reasoning_content", "")
            fixed_msgs.append(m)

        body = {
            "model": self.config.model,
            "messages": fixed_msgs,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "tools": tools,
            "tool_choice": "auto",
        }

        resp = await self._http.post(
            f"{self.base_url}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=body,
        )

        if resp.status_code != 200:
            raise Exception(f"DeepSeek retry failed {resp.status_code}: {resp.json()}")

        data = resp.json()
        choice = data["choices"][0]
        msg = choice["message"]
        usage = data.get("usage", {})

        tool_calls = []
        for tc in (msg.get("tool_calls") or []):
            tool_calls.append({
                "id": tc["id"],
                "type": "function",
                "function": {
                    "name": tc["function"]["name"],
                    "arguments": tc["function"]["arguments"],
                }
            })

        return LLMResponse(
            content=msg.get("content") or "",
            tool_calls=tool_calls,
            usage={
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
            },
            finish_reason=choice.get("finish_reason", ""),
        )


# ============================================================
# Doubao（火山引擎）实现 — OpenAI 兼容接口，支持多模态
# ============================================================

class DoubaoProvider(LLMProvider):
    """火山引擎 Doubao API — 直接 HTTP 调用，支持多模态"""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        import httpx
        self._http = httpx.AsyncClient(timeout=120)
        self.base_url = (config.base_url or "https://ark.cn-beijing.volces.com/api/v3").rstrip("/")
        self.api_key = config.api_key

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _build_body(self, messages: list, tools: list = None,
                    system_prompt: str = None, stream: bool = False) -> dict:
        msgs = self._format_messages(messages, system_prompt)
        cleaned = []
        for m in msgs:
            m = dict(m)
            if m.get("role") == "assistant" and m.get("content") == "":
                if m.get("tool_calls"):
                    m["content"] = None
            cleaned.append(m)
        body = {
            "model": self.config.model,
            "messages": cleaned,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        if stream:
            body["stream"] = True
        return body

    def _parse_response(self, resp) -> LLMResponse:
        if resp.status_code != 200:
            raise Exception(f"Doubao API error {resp.status_code}: {resp.json()}")
        data = resp.json()
        choice = data["choices"][0]
        msg = choice["message"]
        usage = data.get("usage", {})
        tool_calls = []
        for tc in (msg.get("tool_calls") or []):
            tool_calls.append({
                "id": tc["id"], "type": "function",
                "function": {"name": tc["function"]["name"], "arguments": tc["function"]["arguments"]}
            })
        return LLMResponse(
            content=msg.get("content") or "", tool_calls=tool_calls,
            usage={"prompt_tokens": usage.get("prompt_tokens", 0), "completion_tokens": usage.get("completion_tokens", 0)},
            finish_reason=choice.get("finish_reason", ""),
        )

    async def chat(self, messages: list, tools: list = None,
                   system_prompt: str = None) -> LLMResponse:
        body = self._build_body(messages, tools, system_prompt)
        resp = await self._http.post(
            f"{self.base_url}/chat/completions", headers=self._headers(), json=body)
        return self._parse_response(resp)

    async def chat_stream(self, messages: list, tools: list = None,
                          system_prompt: str = None):
        body = self._build_body(messages, tools, system_prompt, stream=True)
        accumulated_text = ""
        accumulated_tool_calls: dict[int, dict] = {}
        async with self._http.stream(
            "POST", f"{self.base_url}/chat/completions",
            headers=self._headers(), json=body,
        ) as resp:
            if resp.status_code != 200:
                err_body = await resp.aread()
                yield {"type": "error", "content": f"API Error {resp.status_code}: {err_body.decode()[:200]}"}
                return
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                payload = line[6:].strip()
                if payload == "[DONE]":
                    break
                try:
                    chunk = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                choices = chunk.get("choices", [])
                if not choices:
                    continue
                delta = choices[0].get("delta", {})
                content = delta.get("content")
                if content:
                    accumulated_text += content
                    yield {"type": "token", "content": content}
                tc_delta = delta.get("tool_calls")
                if tc_delta:
                    for tc in tc_delta:
                        idx = tc.get("index", 0)
                        if idx not in accumulated_tool_calls:
                            accumulated_tool_calls[idx] = {
                                "id": tc.get("id", f"call_{idx}"), "type": "function",
                                "function": {"name": "", "arguments": ""},
                            }
                        fn = tc.get("function", {})
                        if fn.get("name"):
                            accumulated_tool_calls[idx]["function"]["name"] += fn["name"]
                        if fn.get("arguments"):
                            accumulated_tool_calls[idx]["function"]["arguments"] += fn["arguments"]
        tool_calls = [v for _, v in sorted(accumulated_tool_calls.items())] if accumulated_tool_calls else []
        yield {"type": "done", "content": accumulated_text, "tool_calls": tool_calls}


# ============================================================
# 工厂方法
# ============================================================

_provider: LLMProvider | None = None


def get_provider(config: LLMConfig = None) -> LLMProvider:
    """获取 LLM 提供者实例（单例）"""
    global _provider
    if _provider is None:
        cfg = config or load_config()
        providers = {
            "openai": OpenAIProvider,
            "claude": ClaudeProvider,
            "deepseek": DeepSeekProvider,
            "doubao": DoubaoProvider,
        }
        cls = providers.get(cfg.provider)
        if cls is None:
            raise ValueError(f"不支持的 LLM 提供商: {cfg.provider}，可选: {list(providers.keys())}")
        _provider = cls(cfg)
    return _provider


def reset_provider():
    """重置提供者（切换模型时调用）"""
    global _provider
    _provider = None
