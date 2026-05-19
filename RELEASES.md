# 胶片伴侣 AI — 上线记录

## 2026-05-19 10:06 | `e5109c8`

| 项目 | 内容 |
|------|------|
| 版本 | `e5109c8` |
| 日期 | 2026-05-19 10:06 |
| 类型 | feat |
| 部署方式 | 方案 B（完整构建） |
| 部署人 | laigz |

**变更内容**

- feat: 登录体系 — 弹窗注册/登录 + JWT + 无感刷新 + 单点登录

**涉及文件 （7 files, +1132/-36）**

| 文件 | 改动 |
|------|------|
| `web/auth.py` | 新增：注册/登录/刷新/登出/用户信息 API |
| `web/server.py` | 所有 API 加 `Depends(get_current_user)` 保护 |
| `web/chat.html` | 登录弹窗 + fetch 拦截器 + 无感刷新 + 单点登出提示 |
| `web/data.html` | 同步适配 auth |
| `db/schema.py` | JWT 工具 + 密码哈希 + 用户 CRUD + token_version |
| `db/pool.py` | users 表 DDL |
| `config/init.sql` | PostgreSQL 兼容 users 表 |

**验证结果**

| 检查项 | 结果 |
|--------|------|
| 容器状态 | ✅ Up 8 seconds |
| HTTP 主页 (/) | ✅ 200 |
| HTTP 数据页 (/data) | ✅ 200 |
| 注册 POST /api/auth/register | ✅ ok |
| 登录 POST /api/auth/login | ✅ token returned |
| 认证 GET /api/film | ✅ 200 (user-scoped) |
| 未认证 GET /api/film | ✅ 401 |
| SSE 流式聊天 | ✅ 200 (已验证) |
| 日志 | ✅ 无错误/无异常 |

**注意**
- 旧数据 `user_id='web_user'` 与新用户隔离，需手动迁移
- SSH 用户名是 `root`，项目路径 `/home/aideploy/film-companion`
- 容器名 `film-companion-app-1`（docker compose 命名）
- git pull 前需 `git config --global --add safe.directory /home/aideploy/film-companion`


## 2026-05-19 11:22 | `2be0554`

| 项目 | 内容 |
|------|------|
| 版本 | `2be0554` |
| 日期 | 2026-05-19 11:22 |
| 类型 | feat |
| 部署方式 | 方案 B（完整构建） |
| 部署人 | laigz |

**变更内容**

- feat: Vue 3 前端重构 — 13 个组件，全量替换原生 HTML/CSS/JS
- 5 套可切换主题（极简白/深空灰/暖阳米/暗房红/墨绿）
- 交互参考 ChatGPT/DeepSeek 风格，全屏聊天 + 弹出侧栏
- Vite 构建，输出到 web/dist/，后端自动切换静态目录

**验证结果**

| 检查项 | 结果 |
|--------|------|
| Vue 首页 (`/`) | ✅ 200 (Vue SPA) |
| 注册 POST /api/auth/register | ✅ ok |
| 登录 POST /api/auth/login | ✅ token returned |
| 认证 GET /api/film | ✅ 200 (user-scoped) |
| 日志 | ✅ 无错误 |
