# 胶片伴侣 AI — API 接口文档

> **版本**: 1.0.0 · 最后更新: 2026-05-19
>
> **维护规则**: 每次新增/修改/删除接口，必须同步更新本文档。
> 本文档是前后端联调的唯一依据。

---

## 目录

1. [认证接口](#1-认证接口)
2. [会话管理](#2-会话管理)
3. [聊天接口](#3-聊天接口)
4. [数据查询](#4-数据查询)
5. [页面路由](#5-页面路由)
6. [数据模型](#6-数据模型)
7. [错误码](#7-错误码)
8. [鉴权方式](#8-鉴权方式)

---

## 1. 认证接口

> 前缀: `/api/auth`
> 认证: 除 `register`/`login` 外，均需 `Authorization: Bearer <access_token>`

### 1.1 注册

```http
POST /api/auth/register
Content-Type: application/json

{
    "username": "demo",       // string, 2-32 字符
    "password": "demo123"     // string, 至少 6 位
}
```

**成功响应 (200):**
```json
{
    "status": "ok",
    "access_token": "eyJhbG...",     // JWT, 有效期 15 分钟
    "refresh_token": "eyJhbG...",    // JWT, 有效期 7 天
    "expires_in": 900,
    "user": {
        "id": "uuid-string",
        "username": "demo"
    }
}
```

**错误响应:**
| 状态码 | detail | 说明 |
|--------|--------|------|
| 400 | 用户名长度需在 2-32 个字符之间 | 参数校验 |
| 400 | 密码长度至少 6 位 | 参数校验 |
| 409 | 用户名已存在 | 用户名冲突 |

---

### 1.2 登录

```http
POST /api/auth/login
Content-Type: application/json

{
    "username": "demo",
    "password": "demo123"
}
```

**成功响应 (200):** 同注册，返回双 token

| 状态码 | detail | 说明 |
|--------|--------|------|
| 401 | 用户名或密码错误 | 认证失败 |

---

### 1.3 刷新 Token

```http
POST /api/auth/refresh
Content-Type: application/json

{
    "refresh_token": "eyJhbG..."    // 注册/登录时获取的 refresh_token
}
```

**成功响应 (200):**
```json
{
    "status": "ok",
    "access_token": "eyJhbG...",
    "expires_in": 900
}
```

| 状态码 | detail | 说明 |
|--------|--------|------|
| 401 | refresh_token 已过期或无效 | token 过期 |
| 401 | 登录已失效，请重新登录 | 单点登录（在别处登录过） |

---

### 1.4 登出

```http
POST /api/auth/logout
Authorization: Bearer <access_token>
```

**成功响应 (200):**
```json
{
    "status": "ok",
    "message": "已退出登录"
}
```

> **注意**: 登出会递增 `token_version`，使当前用户的所有 token 立即失效。

---

### 1.5 获取当前用户

```http
GET /api/auth/me
Authorization: Bearer <access_token>
```

**成功响应 (200):**
```json
{
    "status": "ok",
    "user": {
        "id": "uuid-string",
        "username": "demo",
        "token_version": 3,
        "phone": null,
        "status": "active",
        "created_at": "2026-05-19 02:10:06"
    }
}
```

---

## 2. 会话管理

> 所有接口需携带 `Authorization: Bearer <access_token>`

### 2.1 获取会话列表

```http
GET /api/sessions?limit=50
Authorization: Bearer <access_token>
```

**成功响应 (200):**
```json
{
    "status": "ok",
    "sessions": [
        {
            "id": "uuid",
            "user_id": "uuid",
            "title": "买的胶卷到了",
            "platform": "web",
            "status": "active",
            "meta": "{}",
            "created_at": "2026-05-19T...",
            "updated_at": "2026-05-19T...",
            "last_activity": "2026-05-19T...",
            "msg_count": 5,
            "last_preview": "帮我查一下库存..."
        }
    ]
}
```

### 2.2 获取会话详情（含消息）

```http
GET /api/sessions/{session_id}
Authorization: Bearer <access_token>
```

| 状态码 | 说明 |
|--------|------|
| 404 | 会话不存在 |
| 403 | 无权访问该会话（非自己的会话） |

### 2.3 创建新会话

```http
POST /api/sessions
Authorization: Bearer <access_token>
```

**成功响应 (200):**
```json
{
    "status": "ok",
    "session_id": "uuid"
}
```

### 2.4 删除会话

```http
DELETE /api/sessions/{session_id}
Authorization: Bearer <access_token>
```

| 状态码 | 说明 |
|--------|------|
| 404 | 会话不存在 |
| 403 | 无权删除该会话 |

---

## 3. 聊天接口

### 3.1 SSE 流式聊天（推荐）

```http
POST /api/chat/stream
Authorization: Bearer <access_token>
Content-Type: application/json

{
    "message": "帮我查一下库存",
    "session_id": "uuid"       // 可选，不传则自动创建新会话
}
```

**响应格式**: Server-Sent Events (`text/event-stream`)

```
data: {"type": "token", "content": "好的"}
data: {"type": "token", "content": "，我来查一下"}
data: {"type": "tool_start", "tools": ["query_film"]}
data: {"type": "tool_result", "name": "query_film", "result": "..."}
data: {"type": "token", "content": "目前库存有..."}
data: {"type": "done", "session_id": "uuid"}
```

| Event type | 说明 |
|------------|------|
| `token` | AI 回复文本片段，前端追加显示 |
| `tool_start` | AI 调用了工具，`tools` 为工具名数组 |
| `tool_result` | 工具执行完成，`name` 工具名，`result` 结果摘要 |
| `done` | 本轮回复完成，`session_id` 为当前会话 ID |
| `error` | 服务端错误 |

### 3.2 非流式聊天（兼容）

```http
POST /api/chat
Authorization: Bearer <access_token>
Content-Type: application/json

{
    "message": "帮我查一下库存",
    "session_id": "uuid"
}
```

**响应:**
```json
{
    "reply": "目前库存有...",
    "session_id": "uuid",
    "tool_calls": [{"name": "query_film", "args": {}}]
}
```

---

## 4. 数据查询

### 4.1 查询胶卷

```http
GET /api/film?film_type=彩色反转片&status=未使用&iso_min=100&sort=created_at&order=DESC&limit=100
Authorization: Bearer <access_token>
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| film_type | string | 否 | 按类型筛选 |
| status | string | 否 | 按状态筛选 |
| iso_min | int | 否 | 最低 ISO |
| sort | string | 否 | 排序字段，默认 `created_at` |
| order | string | 否 | 排序方向，默认 `DESC` |
| limit | int | 否 | 返回条数，默认 100 |

**响应:**
```json
{
    "status": "ok",
    "count": 3,
    "films": [
        {
            "id": "uuid",
            "user_id": "uuid",
            "name": "柯达 Portra 400",
            "film_type": "彩色负片",
            "iso": 400,
            "format": "135",
            "quantity": 5,
            "unit": "卷",
            "purchase_date": null,
            "expiry_date": "2026-12-31",
            "price": 68.0,
            "storage_location": "冰箱",
            "status": "未使用",
            "meta": {},
            "created_at": "...",
            "updated_at": "...",
            "frames": 36,
            "sheet_count": null,
            "purchase_price": 68.0,
            "current_value": null,
            "expiry_status": "ok",            // "ok" | "expiring" | "expired"
            "days_left": 226
        }
    ]
}
```

### 4.2 查询设备

```http
GET /api/gear?gear_type=相机&brand=尼康&status=在用&sort=created_at&order=DESC&limit=100
Authorization: Bearer <access_token>
```

**响应:**
```json
{
    "status": "ok",
    "count": 2,
    "gear": [
        {
            "id": "uuid",
            "user_id": "uuid",
            "name": "尼康 F3",
            "gear_type": "相机",
            "brand": "尼康",
            "model": "F3",
            "status": "在用",
            "purchase_date": "2025-06-15",
            "price": 3500.0,
            "meta": {}
        }
    ]
}
```

### 4.3 获取统计数据

```http
GET /api/stats
Authorization: Bearer <access_token>
```

**响应:**
```json
{
    "status": "ok",
    "stats": {
        "film_count": 12,
        "gear_count": 5,
        "total_film_price": 2050.0,
        "total_gear_price": 15800.0,
        "total_value": 17850.0,
        "film_types": {"彩色负片": 8, "黑白负片": 3, "彩色反转片": 1},
        "gear_types": {"相机": 3, "镜头": 2},
        "film_statuses": {"未使用": 8, "已拍摄": 3, "已冲洗": 1},
        "expired_count": 1,
        "expiring_count": 2
    }
}
```

---

## 5. 页面路由

| 路径 | 方法 | Content-Type | 说明 |
|------|------|-------------|------|
| `/` | GET | `text/html` | 主聊天页面（需在浏览器中登录） |
| `/data` | GET | `text/html` | 数据查看页面（胶卷/设备表格） |

> **注意**: HTML 页面中的 JS 自动处理 token 注入、无感刷新、401 跳转。

---

## 6. 数据模型

### 6.1 users

| 字段 | 类型 | 说明 |
|------|------|------|
| id | TEXT (UUID) | 主键 |
| username | TEXT UNIQUE | 用户名 |
| password_hash | TEXT | pbkdf2_hmac 哈希 |
| token_version | INTEGER | 单点登录版本号 |
| phone | TEXT | 预留：手机号 |
| status | TEXT | 账号状态 |
| created_at | TEXT | 注册时间 |

### 6.2 film

| 字段 | 类型 | 说明 |
|------|------|------|
| id | TEXT (UUID) | 主键 |
| user_id | TEXT | 所属用户 |
| name | TEXT | 胶卷型号名称 |
| film_type | TEXT | 类型（彩色负片/反转片/黑白负片） |
| iso | INTEGER | ISO |
| format | TEXT | 格式（135/120/4x5/5x7/8x10） |
| quantity | INTEGER | 数量 |
| unit | TEXT | 单位（卷/张/盒） |
| frames | INTEGER | 每卷张数（135 胶卷） |
| sheet_count | INTEGER | 张数（大画幅页片） |
| expiry_date | TEXT | 过期日期 |
| price | REAL | 单价 |
| storage_location | TEXT | 存放位置 |
| status | TEXT | 状态（未使用/已拍摄/已冲洗/已扫描） |
| meta | JSON | 扩展字段 |

### 6.3 gear

| 字段 | 类型 | 说明 |
|------|------|------|
| id | TEXT (UUID) | 主键 |
| user_id | TEXT | 所属用户 |
| name | TEXT | 设备名称 |
| gear_type | TEXT | 类型（相机/镜头/三脚架/闪光灯） |
| brand | TEXT | 品牌 |
| model | TEXT | 型号 |
| status | TEXT | 状态（在用/闲置/待出/已出/维修中） |
| price | REAL | 价格 |
| meta | JSON | 扩展字段 |

### 6.4 shoot

| 字段 | 类型 | 说明 |
|------|------|------|
| id | TEXT (UUID) | 主键 |
| user_id | TEXT | 所属用户 |
| title | TEXT | 拍摄活动标题 |
| shoot_date | TEXT | 拍摄日期 |
| location | TEXT | 地点 |
| description | TEXT | 描述 |
| tags | TEXT (JSON array) | 标签 |
| rating | INTEGER | 评分 (1-5) |
| weather | TEXT | 天气 |
| meta | JSON | 扩展字段 |

### 6.5 chat_session

| 字段 | 类型 | 说明 |
|------|------|------|
| id | TEXT (UUID) | 主键 |
| user_id | TEXT | 所属用户 |
| title | TEXT | 自动生成的会话标题 |
| platform | TEXT | 平台（web/cli） |
| last_activity | TEXT | 最后活动时间 |

### 6.6 chat_message

| 字段 | 类型 | 说明 |
|------|------|------|
| id | TEXT (UUID) | 主键 |
| session_id | TEXT | 所属会话 |
| user_id | TEXT | 所属用户 |
| role | TEXT | user/assistant/tool_call/tool_result |
| content | TEXT | 消息内容 |
| turn_index | INTEGER | 轮次序号 |
| meta | JSON | 扩展字段 |

---

## 7. 错误码

| 状态码 | 含义 | 典型场景 |
|--------|------|----------|
| 200 | 成功 | |
| 400 | 请求参数错误 | 消息为空、用户名格式不对 |
| 401 | 未认证 / 认证失效 | 无 token、token 过期、单点登录被踢 |
| 403 | 无权限 | 访问/删除其他用户的数据 |
| 404 | 资源不存在 | 会话 ID 无效 |
| 409 | 资源冲突 | 用户名已存在 |
| 500 | 服务端错误 | LLM 调用失败、数据库异常 |
| 503 | 服务未就绪 | LLM provider 未初始化 |

---

## 8. 鉴权方式

### Token 机制

```
access_token  ── 有效期 15 分钟 ── 用于所有 API 认证
refresh_token ── 有效期 7 天   ── 仅用于刷新 access_token
```

### 请求头格式

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### 前端 Token 刷新流程

```
请求 API
  → 401? → 检查 refresh_token
    → 自动调用 POST /api/auth/refresh
      → 成功: 新 access_token 存入 localStorage, 重试原请求
      → 失败 (token_version 不匹配 / refresh 过期):
        → 弹出登录框 → "登录已失效，请重新登录"
```

### 单点登录

- 每次登录/登出都会递增 `token_version`
- 旧 token 中的 `ver` 与数据库中的 `token_version` 不一致 → 401
- 效果：新登录自动使旧登录的所有 token 失效

### 数据权限

所有查询都按 `user_id` 过滤:
- 用户 A 只能看到自己的胶卷、设备、拍摄记录、会话
- 跨用户访问返回 403 或空结果（取决于具体接口）
