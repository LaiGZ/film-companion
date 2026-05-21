"""
数据迁移脚本：将旧表的数据迁入新的 entities 统一存储

用法：
  python -m db.migrate_to_entities

迁移完成后，旧表保留只读，不删除。
"""

import asyncio
import json
import os
import sys

# 确保项目根目录在路径中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db.pool import execute, init_pool
from db.entity_store import init_entity_store, save_entity


# ============================================================
# 胶卷迁移
# ============================================================

def _film_to_entity(film: dict) -> dict:
    """将旧 film 表的行转换为 entity 的 data JSON"""
    data = {}

    # 基础字段
    if film.get("film_type"):
        data["type"] = film["film_type"]
    if film.get("iso"):
        data["iso"] = film["iso"]
    if film.get("format"):
        data["format"] = film["format"]
    if film.get("quantity") is not None:
        data["quantity"] = film["quantity"]
    if film.get("unit"):
        data["unit"] = film["unit"]
    if film.get("status"):
        data["status"] = film["status"]
    if film.get("storage_location"):
        data["storage"] = film["storage_location"]
    if film.get("frames") is not None:
        try:
            data["frames"] = int(film["frames"])
        except (ValueError, TypeError):
            pass
    if film.get("sheet_count") is not None:
        try:
            data["sheet_count"] = int(film["sheet_count"])
        except (ValueError, TypeError):
            pass

    # 日期
    if film.get("purchase_date"):
        data["purchase"] = data.get("purchase", {})
        data["purchase"]["date"] = film["purchase_date"]
    if film.get("expiry_date"):
        data["expiry"] = film["expiry_date"]

    # 价格
    price = film.get("price") or film.get("purchase_price")
    if price is not None:
        try:
            data["purchase"] = data.get("purchase", {})
            data["purchase"]["price"] = float(price)
            data["purchase"]["currency"] = film.get("currency") or "CNY"
        except (ValueError, TypeError):
            pass

    # 合并旧 meta JSON
    old_meta = film.get("meta", "{}")
    if isinstance(old_meta, str) and old_meta != "{}":
        try:
            meta_dict = json.loads(old_meta)
            data.update(meta_dict)
        except (json.JSONDecodeError, TypeError):
            pass

    # 默认状态
    if "status" not in data:
        data["status"] = "未使用"

    return data


async def migrate_films(user_id: str = None) -> int:
    """迁移 film 表数据到 entities"""
    rows = await execute("SELECT * FROM film")
    if not rows:
        print("  📭 没有胶卷数据需要迁移")
        return 0

    count = 0
    for film in rows:
        target_user = user_id or film.get("user_id", "default")
        data = _film_to_entity(film)
        await save_entity(
            user_id=target_user,
            entity_type="film",
            name=film.get("name", "未命名胶卷"),
            data=data,
            entity_id=film["id"],
        )
        count += 1
        if count % 5 == 0:
            print(f"  → 已迁移 {count}/{len(rows)}...")

    print(f"  ✅ 胶卷迁移完成: {count} 条")
    return count


# ============================================================
# 设备迁移
# ============================================================

def _gear_to_entity(gear: dict) -> dict:
    """将旧 gear 表的行转换为 entity 的 data JSON"""
    data = {}

    if gear.get("gear_type"):
        data["gear_type"] = gear["gear_type"]
    if gear.get("category"):
        data["category"] = gear["category"]
    if gear.get("brand"):
        data["brand"] = gear["brand"]
    if gear.get("model"):
        data["model"] = gear["model"]
    if gear.get("nickname"):
        data["nickname"] = gear["nickname"]
    if gear.get("serial_number"):
        data["serial_number"] = gear["serial_number"]
    if gear.get("camera_type"):
        data["camera_type"] = gear["camera_type"]
    if gear.get("lens_mount"):
        data["lens_mount"] = gear["lens_mount"]
    if gear.get("shutter_type"):
        data["shutter_type"] = gear["shutter_type"]
    if gear.get("format_support"):
        data["format_support"] = gear["format_support"]
    if gear.get("condition"):
        data["condition"] = gear["condition"]
    if gear.get("status"):
        data["status"] = gear["status"]
    if gear.get("storage_location"):
        data["storage"] = gear["storage_location"]

    # 日期
    if gear.get("purchase_date"):
        data["purchase"] = data.get("purchase", {})
        data["purchase"]["date"] = gear["purchase_date"]
    if gear.get("sell_date"):
        data["sell"] = data.get("sell", {})
        data["sell"]["date"] = gear["sell_date"]

    # 价格
    price = gear.get("price") or gear.get("purchase_price")
    if price is not None:
        try:
            data["purchase"] = data.get("purchase", {})
            data["purchase"]["price"] = float(price)
            data["purchase"]["currency"] = gear.get("currency") or "CNY"
        except (ValueError, TypeError):
            pass

    sell_price = gear.get("sell_price")
    if sell_price is not None:
        try:
            data["sell"] = data.get("sell", {})
            data["sell"]["price"] = float(sell_price)
        except (ValueError, TypeError):
            pass

    # 兼容性
    if gear.get("parent_id"):
        data["parent_id"] = gear["parent_id"]
    compat = gear.get("compatible_with")
    if compat and compat != "[]":
        if isinstance(compat, str):
            try:
                data["compatible_with"] = json.loads(compat)
            except (json.JSONDecodeError, TypeError):
                data["compatible_with"] = compat
        else:
            data["compatible_with"] = compat

    # 旧 meta
    old_meta = gear.get("meta", "{}")
    if isinstance(old_meta, str) and old_meta != "{}":
        try:
            meta_dict = json.loads(old_meta)
            data.update(meta_dict)
        except (json.JSONDecodeError, TypeError):
            pass

    return data


async def migrate_gear(user_id: str = None) -> int:
    """迁移 gear 表数据到 entities"""
    rows = await execute("SELECT * FROM gear")
    if not rows:
        print("  📭 没有设备数据需要迁移")
        return 0

    count = 0
    for gear in rows:
        target_user = user_id or gear.get("user_id", "default")
        data = _gear_to_entity(gear)
        await save_entity(
            user_id=target_user,
            entity_type="gear",
            name=gear.get("name", "未命名设备"),
            data=data,
            entity_id=gear["id"],
        )
        count += 1
        if count % 5 == 0:
            print(f"  → 已迁移 {count}/{len(rows)}...")

    print(f"  ✅ 设备迁移完成: {count} 条")
    return count


# ============================================================
# 拍摄记录迁移
# ============================================================

def _shoot_to_entity(shoot: dict) -> dict:
    data = {}

    if shoot.get("title"):
        data["title"] = shoot["title"]
    if shoot.get("shoot_date"):
        data["shoot_date"] = shoot["shoot_date"]
    if shoot.get("location"):
        data["location"] = shoot["location"]
    if shoot.get("description"):
        data["description"] = shoot["description"]
    if shoot.get("weather"):
        data["weather"] = shoot["weather"]
    if shoot.get("rating") is not None:
        data["rating"] = shoot["rating"]
    if shoot.get("status"):
        data["status"] = shoot["status"]

    # tags
    tags = shoot.get("tags", "[]")
    if isinstance(tags, str) and tags != "[]":
        try:
            data["tags"] = json.loads(tags)
        except (json.JSONDecodeError, TypeError):
            data["tags"] = [tags]

    # 旧 meta
    old_meta = shoot.get("meta", "{}")
    if isinstance(old_meta, str) and old_meta != "{}":
        try:
            meta_dict = json.loads(old_meta)
            data.update(meta_dict)
        except (json.JSONDecodeError, TypeError):
            pass

    return data


async def migrate_shoots(user_id: str = None) -> int:
    """迁移 shoot 表数据到 entities"""
    rows = await execute("SELECT * FROM shoot")
    if not rows:
        print("  📭 没有拍摄记录需要迁移")
        return 0

    count = 0
    for shoot in rows:
        target_user = user_id or shoot.get("user_id", "default")
        data = _shoot_to_entity(shoot)
        await save_entity(
            user_id=target_user,
            entity_type="shoot",
            name=shoot.get("title") or shoot.get("location") or "未命名拍摄",
            data=data,
            entity_id=shoot["id"],
        )
        count += 1
        if count % 5 == 0:
            print(f"  → 已迁移 {count}/{len(rows)}...")

    print(f"  ✅ 拍摄记录迁移完成: {count} 条")
    return count


# ============================================================
# 主入口
# ============================================================

async def main():
    print("\n🔄  数据迁移: 旧表 → entities 统一存储")
    print("=" * 50)

    await init_pool()
    await init_entity_store()
    print("✅ 实体表就绪")

    # 检查是否已有数据
    existing = await execute(
        "SELECT COUNT(*) AS cnt FROM entities"
    )
    if existing and existing[0]["cnt"] > 0:
        print(f"⚠️   entities 表已有 {existing[0]['cnt']} 条数据，跳过迁移")
        print("   如需重新迁移，请先清空 entities 表")
        return

    print("\n📦 迁移胶卷...")
    film_count = await migrate_films()

    print("\n📦 迁移设备...")
    gear_count = await migrate_gear()

    print("\n📦 迁移拍摄记录...")
    shoot_count = await migrate_shoots()

    print("\n" + "=" * 50)
    print(f"✅ 迁移完成！")
    print(f"   胶卷: {film_count} 条")
    print(f"   设备: {gear_count} 条")
    print(f"   拍摄: {shoot_count} 条")
    print(f"   总计: {film_count + gear_count + shoot_count} 条")

    # 验证
    verify = await execute(
        """SELECT entity_type, COUNT(*) AS cnt
           FROM entities GROUP BY entity_type"""
    )
    print(f"\n📊 验证:")
    for v in verify:
        print(f"   {v['entity_type']}: {v['cnt']} 条")


if __name__ == "__main__":
    asyncio.run(main())
