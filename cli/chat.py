"""
命令行聊天界面
"""

import asyncio
import json
import os
import sys
from datetime import datetime

from llm.provider import get_provider, load_config, LLMProvider
from plugins.registry import get_registry, PluginRegistry
from memory.context import (
    init_session,
    record_user_message,
    record_assistant_message,
    record_tool_call,
    record_tool_result,
    get_context,
)
from memory.long_term import load_memories_for_session, extract_memories
from db.audit import record_audit


SYSTEM_PROMPT_TEMPLATE = """你是"胶片伴侣 AI"，一个对话式胶片摄影管理助手。

## 你的能力
你可以帮助用户管理胶卷库存、摄影器材。所有操作通过自然语言完成。

### 胶卷管理
- 记录新买的胶卷（型号、数量、ISO、类型、购买地点等）
- 查询库存（按类型、ISO、状态等筛选）
- 修改/补充胶卷信息
- 删除胶卷记录（需用户确认）
- 检查快过期/已过期的胶卷并提醒

### 设备管理
- 记录新买的器材（相机、镜头、三脚架等）
- 查询设备列表（按类型、品牌、状态筛选）
- 修改设备信息（状态流转：在用/闲置/待出/已出/维修中）
- 删除设备记录（需用户确认）

## 操作规则
1. 用户说"买了/入了/收了 ××" → 调用 add_film 或 add_gear
2. 用户说"有哪些/查一下/看看/还有多少" → 调用 query_film 或 query_gear
3. 用户说"快过期了" → 调用 check_expiring_film
4. 用户说"改成/补充/更新" → 先查数据，再调用 update_film 或 update_gear
5. 用户说"删掉/移除" → 先查数据展示给用户确认，再删除
6. 删除操作必须明确得到用户确认后才能执行

## 回答风格
- 简洁友好，像朋友聊天
- 录入完成时，回显关键信息让用户确认
- 查询结果用表格或列表呈现，一目了然
- 胶卷快过期时主动提醒
- 不确定的信息如实告诉用户，不要编造

## 可用工具
你可以调用以下工具来操作数据：
{available_tools}

{memories}"""


async def chat_loop():
    """主聊天循环"""
    print("\n" + "=" * 50)
    print("  🎞️  胶片伴侣 AI v0.1")
    print("  输入你的指令，或输入 /help 查看帮助")
    print("=" * 50 + "\n")

    # 初始化
    config = load_config()
    provider = get_provider(config)
    registry = get_registry()

    # 加载插件
    print("加载插件...")
    plugin_dir = os.path.join(os.path.dirname(__file__), "..", "plugins")
    registry.load_plugins(plugin_dir)
    print(f"已加载 {len(registry.tools)} 个工具\n")

    # 初始化会话
    session_id = await init_session(user_id="default", platform="cli")
    turn_index = 0

    # 加载长期记忆
    memories_text = await load_memories_for_session("default")
    session_messages = []  # 用于会话结束时提取记忆

    # 系统提示
    available_tools = json.dumps(registry.get_tool_descriptions(), indent=2, ensure_ascii=False)
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        available_tools=available_tools,
        memories=memories_text
    )

    while True:
        try:
            # 读取用户输入
            user_input = input("\n🎞️ 你: ").strip()

            # 特殊命令
            if user_input.lower() in ("/exit", "/quit", "退出", "q"):
                print("\n📸 再见！继续记录你的胶片故事 🎞️")
                break

            if user_input.lower() in ("/help", "帮助", "h"):
                print_help()
                continue

            if user_input.lower() == "/stats":
                await show_stats()
                continue

            if not user_input:
                continue

            # 记录用户消息
            turn_index += 1
            msg_id = await record_user_message(session_id, user_input, turn_index)

            # 设置上下文到插件
            from plugins.film import tools as film_tools
            from plugins.gear import tools as gear_tools
            film_tools.set_context(
                user_id="default", session_id=session_id, message_id=msg_id
            )
            gear_tools.set_context(
                user_id="default", session_id=session_id, message_id=msg_id
            )

            # 记录到会话消息列表（用于提取记忆）
            session_messages.append({"role": "user", "content": user_input})

            # --- LLM 调用 ---
            print("  🤔 思考中...", end="\r")

            # 获取最近上下文
            context = await get_context(session_id)

            # 调用 LLM
            response = await provider.chat(
                messages=context + [{"role": "user", "content": user_input}],
                tools=registry.get_tool_descriptions(),
                system_prompt=system_prompt,
            )

            print(" " * 30, end="\r")  # 清除思考提示

            # --- 处理工具调用 ---
            if response.tool_calls:
                for tc in response.tool_calls:
                    tool_name = tc["function"]["name"]
                    tool_args = tc["function"]["arguments"]

                    # 记录工具调用
                    turn_index += 1
                    await record_tool_call(
                        session_id,
                        json.dumps(tc, ensure_ascii=False),
                        turn_index
                    )

                    # 执行工具
                    print(f"  🔧 调用 {tool_name}...")
                    result = registry.execute_tool(tool_name, tool_args)

                    # 记录工具结果
                    turn_index += 1
                    await record_tool_result(
                        session_id,
                        json.dumps({"tool_call_id": tc["id"], "result": result},
                                   ensure_ascii=False),
                        turn_index
                    )

                    # 记录到会话消息列表
                    session_messages.append({
                        "role": "assistant",
                        "content": f"[调用了 {tool_name}]"
                    })

                    # 再次调用 LLM 将结果转为自然语言
                    updated_context = await get_context(session_id)
                    final_response = await provider.chat(
                        messages=updated_context,
                        tools=None,  # 不需要再调工具了
                        system_prompt=system_prompt,
                    )

                    # 输出最终回复
                    print(f"\n🤖 胶片伴侣: {final_response.content}")

                    # 记录 AI 回复
                    turn_index += 1
                    await record_assistant_message(
                        session_id, final_response.content, turn_index
                    )
                    session_messages.append({
                        "role": "assistant", "content": final_response.content
                    })

            else:
                # 纯文本回复
                print(f"\n🤖 胶片伴侣: {response.content}")

                # 记录 AI 回复
                turn_index += 1
                await record_assistant_message(
                    session_id, response.content, turn_index
                )
                session_messages.append({
                    "role": "assistant", "content": response.content
                })

        except KeyboardInterrupt:
            print("\n\n📸 再见！")
            break
        except Exception as e:
            print(f"\n❌ 出错了: {e}")
            import traceback
            traceback.print_exc()
            print("  😅 试试重新说一遍？")


def print_help():
    """打印帮助信息"""
    print("""
📖 使用指南

你可以这样说：

  💡 录入胶卷:
     "买了3卷富士 Provia 100F"
     "今天到货了 Portra 400，ISO 400，买了5卷"
     "记一下，厦门买了卷伊尔福 HP5 黑白"

  🔍 查询库存:
     "我有哪些反转片？"
     "ISO 400 以上的卷还有多少？"
     "快过期的胶卷有哪些？"

  📝 修改记录:
     "上次买的3卷 Provia 改成2卷"
     "这卷已经拍完了"

  📷 设备管理:
     "买了一台 Contax T2，95新"
     "我有哪些相机？"
     "那台哈苏出掉了"

  🗑️ 删除（会先确认）:
     "删掉最近这卷"
     "移除那台相机"

命令:
  /help  显示帮助
  /stats 显示统计信息
  /quit  退出程序
""")


async def show_stats():
    """显示统计信息"""
    from db.schema import query_film, query_gear

    films = await query_film("default", limit=1000)
    gear = await query_gear("default", limit=1000)

    film_count = films["count"]
    gear_count = gear["count"]

    total_price = sum(f.get("price") or 0 for f in films)
    gear_price = sum(g.get("price") or 0 for g in gear)

    print(f"""
📊 统计概览
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
胶卷: {film_count} 条记录
  总价值: ¥{total_price:.0f}
设备: {gear_count} 件
  总价值: ¥{gear_price:.0f}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")


def main():
    """入口函数"""
    try:
        asyncio.run(chat_loop())
    except KeyboardInterrupt:
        print("\n\n👋 再见！")
    finally:
        # 关闭连接池
        import asyncio
        try:
            loop = asyncio.new_event_loop()
            from db.pool import close_pool
            loop.run_until_complete(close_pool())
            loop.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
