#!/usr/bin/env python3
"""
胶片伴侣 AI — 统一入口

用法:
  python main.py              # 启动 Web 服务（默认，端口 8080）
  python main.py --cli        # 启动命令行界面
  python main.py --port 3000  # 指定端口
"""

import argparse
import asyncio
import os
import sys
import uvicorn

# 确保项目根目录在 Python 路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _load_env():
    """加载 .env 文件（如果存在）"""
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                if key and value and not os.environ.get(key):
                    os.environ[key] = value


async def init() -> tuple:
    """初始化公共组件：数据库 + LLM Provider + 插件注册表"""
    _load_env()

    # 1. 数据库
    from db.pool import init_pool
    print("📦 连接数据库...")
    await init_pool()
    print("✅ 数据库连接成功")

    # 2. LLM Provider
    from llm.provider import get_provider, load_config
    config = load_config()
    provider = get_provider(config)
    print(f"✅ LLM 就绪: {config.provider}/{config.model}")

    # 3. 插件
    from plugins.registry import get_registry
    registry = get_registry()
    plugin_dir = os.path.join(os.path.dirname(__file__), "plugins")
    registry.load_plugins(plugin_dir)
    print(f"✅ 插件加载完成: {len(registry.tools)} 个工具")

    return provider, registry


def start_web(provider, registry, port: int = 8080):
    """启动 Web 服务"""
    from web.server import app, init_web_app
    init_web_app(provider, registry)

    print(f"\n🌐  Web 服务已启动: http://localhost:{port}")
    print(f"    💬 对话页面: http://localhost:{port}/")
    print(f"    📊 数据页面: http://localhost:{port}/data")
    print(f"    📖 API 文档: http://localhost:{port}/docs")
    print("    按 Ctrl+C 停止\n")

    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


async def start_cli(provider, registry):
    """启动命令行界面"""
    print("\n  🎞️  胶片伴侣 AI — 命令行模式")
    print("  ============================\n")

    from cli.chat import chat_loop
    await chat_loop()


def main():
    parser = argparse.ArgumentParser(description="胶片伴侣 AI")
    parser.add_argument(
        "--cli", action="store_true", help="启动命令行界面（而非 Web 服务）"
    )
    parser.add_argument(
        "--port", type=int, default=8080, help="Web 服务端口（默认 8080）"
    )
    args = parser.parse_args()

    # 初始化
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    provider, registry = loop.run_until_complete(init())

    try:
        if args.cli:
            loop.run_until_complete(start_cli(provider, registry))
        else:
            start_web(provider, registry, args.port)
    except KeyboardInterrupt:
        print("\n\n👋 再见！")
    finally:
        from db.pool import close_pool
        try:
            loop.run_until_complete(close_pool())
        except Exception:
            pass


if __name__ == "__main__":
    main()
