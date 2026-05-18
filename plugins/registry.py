"""
插件管理器 — 自动扫描、加载、路由工具
"""

import asyncio
import importlib
import json
import os
from typing import Any

import yaml


# ============================================================
# 工具注册表
# ============================================================

class PluginRegistry:
    """插件注册表，管理所有已加载的工具"""

    def __init__(self):
        self.tools: list[dict] = []           # LLM 可用的工具描述
        self.handlers: dict[str, callable] = {}  # 工具名 → 函数
        self.plugins: dict[str, dict] = {}    # 插件名 → 插件信息
        self.initialized = False

    def load_plugins(self, plugin_dir: str = None):
        """扫描并加载所有插件"""
        if plugin_dir is None:
            plugin_dir = os.path.join(os.path.dirname(__file__))

        for item in os.listdir(plugin_dir):
            plugin_path = os.path.join(plugin_dir, item)
            manifest_path = os.path.join(plugin_path, "manifest.yaml")
            tools_path = os.path.join(plugin_path, "tools.py")

            if not os.path.isdir(plugin_path) or not os.path.exists(manifest_path):
                continue
            if item.startswith("__"):
                continue

            self._load_single_plugin(item, plugin_path, manifest_path, tools_path)

        self.initialized = True

    def _load_single_plugin(self, name: str, plugin_path: str,
                            manifest_path: str, tools_path: str):
        """加载单个插件"""
        # 读取 manifest
        with open(manifest_path) as f:
            manifest = yaml.safe_load(f)

        plugin_info = {
            "name": name,
            "manifest": manifest,
            "path": plugin_path,
        }

        # 动态导入 tools 模块
        try:
            # 相对导入：plugins.{name}.tools
            module_name = f"plugins.{name}.tools"
            tools_module = importlib.import_module(module_name)
        except ImportError:
            print(f"  ⚠️  插件 {name}: 无法导入 tools 模块")
            return

        # 注册工具
        tool_defs = manifest.get("tools", [])
        for tool_def in tool_defs:
            tool_name = tool_def["name"]
            handler_name = tool_def.get("handler", tool_name)

            handler = getattr(tools_module, handler_name, None)
            if handler is None:
                print(f"  ⚠️  插件 {name}: 工具 {tool_name} 未找到处理函数 {handler_name}")
                continue

            # 转换为 OpenAI 工具格式
            openai_tool = {
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": tool_def.get("description", ""),
                    "parameters": self._convert_parameters(tool_def.get("parameters", [])),
                }
            }

            self.tools.append(openai_tool)
            self.handlers[tool_name] = handler

        plugin_info["tool_count"] = len(tool_defs)
        self.plugins[name] = plugin_info
        print(f"  ✅ 加载插件: {name} ({len(tool_defs)} 个工具)")

    def _convert_parameters(self, params: list) -> dict:
        """将 manifest 中的参数定义转为 OpenAI JSON Schema"""
        properties = {}
        required = []

        for p in params:
            ptype = p.get("type", "string")
            json_type = {
                "string": "string",
                "integer": "integer",
                "number": "number",
                "boolean": "boolean",
                "object": "object",
                "array": "array",
            }.get(ptype, "string")

            prop = {
                "type": json_type,
                "description": p.get("description", ""),
            }

            # 枚举类型
            if "enum" in p:
                prop["enum"] = p["enum"]

            properties[p["name"]] = prop

            if p.get("required", False):
                required.append(p["name"])

        return {
            "type": "object",
            "properties": properties,
            "required": required,
        }

    def execute_tool(self, tool_name: str, arguments: str | dict) -> Any:
        """执行一个工具函数，返回结果（同步版本）"""
        handler, args = self._resolve_handler(tool_name, arguments)
        if isinstance(handler, str):
            return {"error": handler}

        try:
            result = handler(**args)
            return result
        except Exception as e:
            return {"error": str(e)}

    async def execute_tool_async(self, tool_name: str, arguments: str | dict) -> Any:
        """执行一个工具函数（异步版本，支持 async 工具）"""
        handler, args = self._resolve_handler(tool_name, arguments)
        if isinstance(handler, str):
            return {"error": handler}

        try:
            if asyncio.iscoroutinefunction(handler):
                result = await handler(**args)
            else:
                result = handler(**args)
            return result
        except Exception as e:
            return {"error": str(e)}

    def _resolve_handler(self, tool_name: str, arguments: str | dict) -> tuple:
        """解析工具名和参数"""
        if tool_name not in self.handlers:
            return f"未知工具: {tool_name}", None

        handler = self.handlers[tool_name]

        if isinstance(arguments, str):
            try:
                args = json.loads(arguments)
            except json.JSONDecodeError:
                return f"参数解析失败: {arguments}", None
        else:
            args = arguments

        return handler, args

    def get_tool_descriptions(self) -> list[dict]:
        """获取所有已加载的工具描述（给 LLM）"""
        return self.tools

    def list_plugins(self) -> list[str]:
        """列出已加载的插件"""
        return list(self.plugins.keys())


# ============================================================
# 全局单例
# ============================================================

_registry: PluginRegistry | None = None


def get_registry() -> PluginRegistry:
    """获取插件注册表单例"""
    global _registry
    if _registry is None:
        _registry = PluginRegistry()
    return _registry


def reload_plugins():
    """重新加载所有插件"""
    global _registry
    _registry = PluginRegistry()
    _registry.load_plugins()
    return _registry
