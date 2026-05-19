# 前端重构计划 — Vue 3

> **状态**: 计划阶段 · **目标**: 用 Vue 3 + Vite 替换现有 2360 行原生 HTML/CSS/JS
>
> 现有前端: `chat.html` (~1400行, 28个函数) + `data.html` (~750行, 11个函数) + 内联CSS
> 后端 API: 13 个接口 (全部已稳定, GET-only 数据查询、POST 流式聊天、auth 认证)

---

## 1. 构建方案

```yaml
构建工具: Vite 6
框架: Vue 3.5 (Composition API + <script setup>)
语言: JavaScript (非 TypeScript, 减少配置)
路由: vue-router 4 (hash 模式, 兼容现有 /data 路径)
状态管理: Pinia
HTTP 客户端: 原生 fetch (封装 composable)
CSS: 保留 CSS 变量体系, 迁移到单个 variables.css
包管理: pnpm (也可用 npm, 看环境)
```

### 目录结构

```
web/
├── index.html                  # Vite 入口
├── src/
│   ├── main.js                 # 应用启动 (router + pinia)
│   ├── App.vue                 # 根组件 (auth guard + 全局布局)
│   │
│   ├── assets/
│   │   └── variables.css       # CSS 变量 (暗色/亮色)
│   │
│   ├── composables/            # 可复用组合式函数
│   │   ├── useAuth.js          # token 管理 + 无感刷新 + 登录弹窗
│   │   ├── useChat.js          # SSE 流式聊天 + 轮次控制
│   │   ├── useSessions.js      # 会话 CRUD
│   │   └── useTheme.js         # 暗色/亮色切换
│   │
│   ├── stores/                 # Pinia 状态
│   │   ├── authStore.js        # 用户状态 + token
│   │   ├── chatStore.js        # 当前会话 + 消息列表 + 流式状态
│   │   └── dataStore.js        # 胶卷/设备/统计 数据
│   │
│   ├── router/
│   │   └── index.js            # 路由定义
│   │
│   ├── pages/                  # 页面级组件
│   │   ├── ChatPage.vue        # / — 主聊天页
│   │   └── DataPage.vue        # /data — 数据查看页
│   │
│   └── components/             # 可复用组件
│       ├── AuthModal.vue       # 登录/注册弹窗
│       ├── Sidebar.vue         # 会话列表侧栏
│       ├── ChatHeader.vue      # 顶部栏 (会话标题 + 用户信息)
│       ├── MessageList.vue     # 消息列表 (含欢迎页)
│       ├── MessageBubble.vue   # 单条消息气泡
│       ├── InputArea.vue       # 输入框 + 发送按钮
│       ├── StreamingIndicator.vue  # 工具调用/打字指示器
│       ├── StatsCards.vue      # 统计卡片组 (data页面)
│       ├── FilterBar.vue       # 筛选栏 (data页面)
│       └── DataTable.vue       # 通用数据表格 (film/gear共用)
│
├── chat.html       # 重构后改为 index.html,
└── data.html       # 重构后由 Vue Router 接管
```

> **关键决策**: 不拆成 MPA (多页面), 改用 SPA + Vue Router.
> `chat.html` 变成 `index.html` (Vite 入口), 原有 `/data` 路由保留, 由 Vite 代理到 Vue Router.

---

## 2. 组件树与数据流

```
App.vue
├── AuthModal.vue                ← 全局弹窗 (由 authStore 控制显隐)
│
├── <router-view>
│   │
│   ├── ChatPage.vue             ← 路径: /
│   │   ├── ChatHeader.vue       ← 显示会话标题 + 用户信息 + 主题切换
│   │   ├── Sidebar.vue          ← 会话列表 (滑出式, 移动端 overlay)
│   │   ├── MessageList.vue      ← 滚动容器
│   │   │   └── MessageBubble.vue (v-for)  ← user/assistant 气泡
│   │   ├── StreamingIndicator.vue  ← 工具调用动画 + 打字指示
│   │   └── InputArea.vue        ← 多行输入 + 发送
│   │
│   └── DataPage.vue             ← 路径: /data
│       ├── StatsCards.vue       ← 4 个统计卡片
│       ├── FilterBar.vue        ← tab 切换 + 下拉筛选
│       └── DataTable.vue        ← 通用表格 (film/gear 共用)
```

### 数据流方向

```
后端 API (FastAPI)
    ↑ fetch (with Bearer token)
    ↓
composables (useAuth / useChat / useSessions)
    ↓
Pinia Stores (authStore / chatStore / dataStore)
    ↓
组件 (通过 computed / watch 响应式读取)
```

---

## 3. 任务清单

### Phase 1 — 项目脚手架

| # | 任务 | 预计 | 依赖 |
|---|------|------|------|
| 1.1 | 创建 Vite + Vue 3 项目 | 10min | — |
| 1.2 | 安装 pinia, vue-router | 5min | 1.1 |
| 1.3 | 配置 vite.config (代理 /api 到后端) | 10min | 1.1 |
| 1.4 | 迁移 CSS 变量 → `variables.css` | 15min | — |
| 1.5 | 配置开发代理: `localhost:5173` → `localhost:8080` | 5min | 1.3 |

### Phase 2 — 全局基础设施

| # | 任务 | 预计 | 依赖 |
|---|------|------|------|
| 2.1 | `authStore.js` — token 存取、token_version、登录态 | 20min | 1.2 |
| 2.2 | `useAuth.js` — fetch 拦截器 (自动注入 Bearer + 401 无感刷新) | 30min | 2.1 |
| 2.3 | `useTheme.js` — CSS 变量切换 + localStorage 持久化 | 10min | 1.4 |
| 2.4 | `router/index.js` — / 和 /data 路由 + auth guard | 10min | 2.1 |
| 2.5 | `App.vue` — auth guard 逻辑 (未登录弹窗) | 15min | 2.1, 2.2, 2.4 |
| 2.6 | `AuthModal.vue` — 登录/注册双表单 | 30min | 2.1 |

### Phase 3 — 聊天页面

| # | 任务 | 预计 | 依赖 |
|---|------|------|------|
| 3.1 | `chatStore.js` — 当前会话 ID、消息列表、流式状态 | 20min | 2.1 |
| 3.2 | `useChat.js` — SSE fetch + token 解析 + 工具调用 | 40min | 3.1 |
| 3.3 | `useSessions.js` — 会话列表 CRUD | 15min | 2.1 |
| 3.4 | `ChatPage.vue` — 主布局 (flex sidebar + chat area) | 15min | 3.1 |
| 3.5 | `Sidebar.vue` — 会话列表 + 新建按钮 + 移动端滑出 | 25min | 3.3 |
| 3.6 | `ChatHeader.vue` — 会话标题 + 用户信息 + 主题/退出 | 15min | 2.3, 2.1 |
| 3.7 | `MessageList.vue` — 滚动容器 + 欢迎页 + 自动滚到底 | 20min | 3.1 |
| 3.8 | `MessageBubble.vue` — 用户/AI 气泡 + Markdown 渲染 | 20min | — |
| 3.9 | `InputArea.vue` — 多行输入 + 发送 + Enter/Shift+Enter | 15min | 3.2 |
| 3.10 | `StreamingIndicator.vue` — 打字指示 + 工具调用动画 | 15min | 3.2 |

### Phase 4 — 数据页面

| # | 任务 | 预计 | 依赖 |
|---|------|------|------|
| 4.1 | `dataStore.js` — film/gear/stats 数据获取 | 20min | 2.1 |
| 4.2 | `DataPage.vue` — 主布局 (stats + tabs + table) | 10min | 4.1 |
| 4.3 | `StatsCards.vue` — 统计卡片渲染 | 15min | 4.1 |
| 4.4 | `FilterBar.vue` — tab 切换 + 下拉筛选 + 刷新 | 20min | 4.1 |
| 4.5 | `DataTable.vue` — 通用表格 (排序、空状态、分页) | 30min | — |

### Phase 5 — 集成测试与部署

| # | 任务 | 预计 | 依赖 |
|---|------|------|------|
| 5.1 | 开发环境联调 (Vite proxy → FastAPI) | 15min | 全部 Phase 3-4 |
| 5.2 | 构建 `vite build` → 输出到 web/dist/ | 5min | 5.1 |
| 5.3 | 更新后端: 静态文件挂载从 `web/` 改为 `web/dist/` | 15min | 5.2 |
| 5.4 | Docker 部署 + 验证 | 15min | 5.3 |
| 5.5 | 更新 API.md (如果前端路由有变化) | 5min | — |

> **总计**: ~420min (7h) — 单人开发, 含调试时间

---

## 4. 核心实现要点

### 4.1 无感刷新 (useAuth.js)

```javascript
// 关键设计: 全局 fetch 拦截 + 刷新队列锁
let _refreshing = null

export function useAuth() {
  // store 中的 refreshToken()
  // fetch 拦截器: 401 → 锁 → refresh → 重试 → 失败 → 弹登录框
  // 单点登录: API 返回 {detail: "该账号已在其他地方登录"} → 弹窗提示
}
```

### 4.2 SSE 流式聊天 (useChat.js)

```javascript
export function useChat() {
  const chatStore = useChatStore()
  
  async function sendMessage(text) {
    // 1. 确保有当前会话 (没有则新建)
    // 2. POST /api/chat/stream (带 Bearer token)
    // 3. 逐行解析 SSE: type: token / tool_start / tool_result / done
    // 4. 流式写入 chatStore.currentMessage
    // 5. done 事件: finalize → 刷新会话列表
    // 6. 工具调用: 显示工具指示器
  }
}
```

### 4.3 CSS 变量迁移

```css
/* variables.css — 和现有体系完全一致 */
:root {
  --bg: #1a1a2e;
  --surface: #16213e;
  --primary: #e94560;
  /* ... 所有变量 */
}

body.light {
  --bg: #f8f6f2;
  /* ... 浅色变量覆盖 */
}
```

Vue 中使用: `document.body.classList.toggle('light')` + `useTheme()` composable.

### 4.4 主题切换实现

```javascript
// useTheme.js
export function useTheme() {
  const isLight = ref(localStorage.getItem('theme') === 'light')
  
  watch(isLight, (val) => {
    document.body.classList.toggle('light', val)
    localStorage.setItem('theme', val ? 'light' : 'dark')
  })
  
  return { isLight, toggle: () => isLight.value = !isLight.value }
}
```

---

## 5. 测试用例

### 5.1 认证流程

| # | 测试用例 | 操作步骤 | 期望结果 |
|---|---------|---------|---------|
| T1 | 未登录访问首页 | 清除 localStorage → 访问 / | 弹出登录弹窗，无法使用聊天功能 |
| T2 | 注册新用户 | 填写用户名+密码 → 点击注册 | 注册成功后弹窗关闭，进入聊天界面 |
| T3 | 注册失败: 用户名过短 | 输入 1 位用户名 → 注册 | 弹窗显示错误提示 |
| T4 | 注册失败: 密码过短 | 输入 5 位密码 → 注册 | 弹窗显示"密码至少6位" |
| T5 | 注册失败: 密码不一致 | 两次输入不同密码 → 注册 | 弹窗显示"两次密码不一致" |
| T6 | 注册失败: 用户名已存在 | 用已注册的用户名再注册 | 弹窗显示"用户名已存在" |
| T7 | 登录成功 | 输入已注册的账号密码 → 登录 | 弹窗关闭，进入聊天，显示用户名 |
| T8 | 登录失败: 错误密码 | 输入错误密码 → 登录 | 弹窗显示"用户名或密码错误" |
| T9 | 登出 | 点击右上角"退出" | 弹窗重新出现，聊天内容清空 |
| T10 | 刷新页面保持登录 | 登录后刷新浏览器 | 保持登录状态，不需要重新登录 |
| T11 | 单点登录 | 用户 A 登录 → 另一设备登录同一账号 | 第一设备弹窗提示"已在其他地方登录" |

### 5.2 Token 无感刷新

| # | 测试用例 | 操作步骤 | 期望结果 |
|---|---------|---------|---------|
| T12 | access_token 过期自动刷新 | mock 15分钟后发请求 | 自动调用 refresh API，业务请求成功返回 |
| T13 | refresh_token 过期 | 修改 refresh_token 为过期值 → 发请求 | 弹窗提示"登录已失效" |
| T14 | 并发请求全部 401 | 同时发 3 个请求，access 全过期 | 只发起一次 refresh，成功后全部重试成功 |

### 5.3 会话管理

| # | 测试用例 | 操作步骤 | 期望结果 |
|---|---------|---------|---------|
| T15 | 首次登录自动创建会话 | 新用户登录 | 侧栏显示一个空白会话 |
| T16 | 发送消息自动生成标题 | 发送第一条消息 "买了3卷Portra 400" | 会话标题变为"买了3卷Portra..." |
| T17 | 切换会话 | 点击侧栏另一个会话 | 加载该会话的历史消息 |
| T18 | 新建会话 | 点击"＋"按钮 | 清空聊天区，侧栏新增会话 |
| T19 | 移动端侧栏关闭 | 点击侧栏外遮罩 / 点击 ✕ 按钮 | 侧栏滑回 |

### 5.4 流式聊天

| # | 测试用例 | 操作步骤 | 期望结果 |
|---|---------|---------|---------|
| T20 | 纯文本回复 | 问"你好" | AI 回复逐 token 显示，打字指示消失 |
| T21 | 工具调用 + 回复 | 说"查一下库存" | 显示"🔧 正在查询..." → 工具执行 → AI 回复 |
| T22 | Markdown 渲染 | AI 回复包含表格/列表 | 正确渲染为 HTML 表格 |
| T23 | 中途切换会话 | 正在流式输出时点击其他会话 | 当前流式中断，切换成功 |
| T24 | 空消息不发送 | 输入框为空点击发送 | 无反应，不调 API |
| T25 | 连续多轮对话 | 发消息 → AI 回复 → 再发消息 | 上下文连贯 |

### 5.5 数据页面

| # | 测试用例 | 操作步骤 | 期望结果 |
|---|---------|---------|---------|
| T26 | 统计卡片加载 | 进入 /data | 4 个卡片显示正确的数字 |
| T27 | Tab 切换 | 点击"胶卷"→"设备" | 表格数据切换，筛选栏联动 |
| T28 | 筛选 | 选择"彩色负片"→ 刷新 | 表格只显示彩色负片 |
| T29 | 排序 | 点击"ISO"列头 | 按 ISO 升序/降序切换 |
| T30 | 空列表 | 筛选出一个不存在的结果 | 显示"没有数据"空状态 |
| T31 | 移动端适配 | 手机宽度 <768px | 表格水平滚动，卡片自适应 |

### 5.6 边界情况

| # | 测试用例 | 操作步骤 | 期望结果 |
|---|---------|---------|---------|
| T32 | 后端未启动 | 启动前端，后端没开 | 友好提示，不白屏崩溃 |
| T33 | 网络断连 | 发消息途中断网 | 显示"网络错误"，不丢失已发消息 |
| T34 | 超长消息 | 发一篇 10000 字文章 | 输入框正常，发送后 AI 正常处理 |
| T35 | 快速双击发送 | 连按两次发送按钮 | 只发一次，不重复 |
| T36 | 暗色/亮色切换 | 点击主题按钮 | 全局立即切换，刷新后保持 |

---

## 6. 开发顺序

```
Phase 1: 脚手架
    ↓
Phase 2: 基础设施 (auth + theme + router + App.vue)
    ↓
Phase 3: 聊天页面 (ChatPage 及其子组件)
    ↓  (完成后即可在 / 下正常使用)
Phase 4: 数据页面 (DataPage 及其子组件)
    ↓
Phase 5: 集成、构建、部署
```

**关键里程碑**:
- Phase 2 完成后: 可注册/登录
- Phase 3 完成后: 可正常聊天 (等于现有 chat.html 功能全部覆盖)
- Phase 4 完成后: 可查看数据 (等于完整覆盖)
- Phase 5 完成后: 新前端正式上线

---

## 7. 现有功能对照清单

> 确保重构后不丢任何功能

| # | 现有功能 | 状态 | 对应组件 |
|---|---------|------|---------|
| 1 | 登录/注册弹窗 (双表单切换) | ✅ | AuthModal |
| 2 | 无感刷新 access_token | ✅ | useAuth |
| 3 | 单点登录提示 | ✅ | useAuth + AuthModal |
| 4 | 退出登录 | ✅ | AuthModal |
| 5 | 会话列表 (标题+预览) | ✅ | Sidebar |
| 6 | 新建会话 | ✅ | Sidebar |
| 7 | 切换会话 | ✅ | Sidebar + ChatPage |
| 8 | 自动标题生成 | ✅ | useChat |
| 9 | 移动端侧栏滑出 + ✕ 关闭 | ✅ | Sidebar |
| 10 | 遮罩关闭侧栏 | ✅ | Sidebar |
| 11 | SSE 流式逐 token 显示 | ✅ | useChat + MessageBubble |
| 12 | 工具调用指示器 | ✅ | StreamingIndicator |
| 13 | Markdown 渲染 (表格/列表) | ✅ | MessageBubble (marked.js) |
| 14 | 欢迎页 (建议按钮) | ✅ | MessageList |
| 15 | 暗色/亮色主题切换 | ✅ | useTheme |
| 16 | 主题持久化 (localStorage) | ✅ | useTheme |
| 17 | iOS 安全区域适配 | ✅ | index.html + CSS |
| 18 | 防 iOS 缩放 (16px font) | ✅ | index.html |
| 19 | 数据统计卡片 (4个) | ✅ | StatsCards |
| 20 | Tab 切换 (胶卷/设备) | ✅ | FilterBar |
| 21 | 筛选项 (类型/状态) | ✅ | FilterBar |
| 22 | 排序 (点击列头) | ✅ | DataTable |
| 23 | 过期状态彩色徽章 | ✅ | DataTable |
| 24 | 空状态提示 | ✅ | DataTable |
| 25 | 数据权限: 只能看自己的 | ✅ | (后端保障, 前端不变) |
| 26 | 多轮对话 (最多 5 轮工具) | ✅ | useChat |
