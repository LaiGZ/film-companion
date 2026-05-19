<template>
  <aside class="sidebar" @click.stop>
    <div class="sidebar-header">
      <span class="sidebar-title">📋 会话</span>
      <div class="sidebar-actions">
        <button class="sidebar-btn" @click="handleNew" title="新建会话">＋</button>
        <button class="sidebar-btn close-btn" @click="$emit('close')" title="关闭">✕</button>
      </div>
    </div>
    <div class="sidebar-list">
      <div
        v-for="s in store.sessions"
        :key="s.id"
        class="sidebar-item"
        :class="{ active: s.id === store.currentSessionId }"
        @click="handleSwitch(s.id)"
      >
        <div class="item-title">{{ s.title || '新会话' }}</div>
        <div v-if="s.last_preview" class="item-preview">{{ s.last_preview }}</div>
        <div class="item-meta">{{ formatTime(s.last_activity) }}</div>
      </div>
      <div v-if="store.sessions.length === 0" class="sidebar-empty">
        暂无会话
      </div>
    </div>
  </aside>
</template>

<script setup>
import { onMounted, onUnmounted } from 'vue'
import { useChatStore } from '@/stores/chatStore'
import { useSessions } from '@/composables/useSessions'

defineEmits(['close'])

const store = useChatStore()
const { createSession, switchSession, loadSessions } = useSessions()

onMounted(() => {
  loadSessions()
  // 监听窗口 resize —— 桌面自动展开
  const mql = window.matchMedia('(min-width: 768px)')
  // 不做自动展开，保持用户选择
})

async function handleNew() {
  await createSession()
}

async function handleSwitch(id) {
  await switchSession(id)
}

function formatTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const now = new Date()
  const diff = (now - d) / 1000
  if (diff < 60) return '刚刚'
  if (diff < 3600) return Math.floor(diff / 60) + '分钟前'
  if (diff < 86400) return Math.floor(diff / 3600) + '小时前'
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}
</script>

<style scoped>
.sidebar {
  width: 280px;
  background: var(--sidebar-bg);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  overflow: hidden;
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.sidebar-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text2);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.sidebar-actions {
  display: flex;
  gap: 6px;
  align-items: center;
}

.sidebar-btn {
  background: none;
  border: none;
  color: var(--text2);
  width: 28px;
  height: 28px;
  border-radius: 6px;
  font-size: 16px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}
.sidebar-btn:hover { background: var(--surface2); color: var(--text); }

.close-btn { display: none; }

.sidebar-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px 0;
}

.sidebar-item {
  padding: 10px 14px;
  cursor: pointer;
  margin: 1px 6px;
  border-radius: var(--radius);
  transition: all 0.15s;
  border-left: 3px solid transparent;
}
.sidebar-item:hover { background: var(--surface2); }
.sidebar-item.active {
  background: var(--surface2);
  border-left-color: var(--primary);
}

.item-title {
  font-size: 14px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 2px;
}

.item-preview {
  font-size: 12px;
  color: var(--text3);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.item-meta {
  font-size: 11px;
  color: var(--text3);
  margin-top: 3px;
}

.sidebar-empty {
  text-align: center;
  padding: 40px 20px;
  color: var(--text3);
  font-size: 13px;
}

@media (max-width: 768px) {
  .sidebar {
    position: fixed;
    left: 0;
    top: 0;
    bottom: 0;
    z-index: 200;
    width: 280px;
    box-shadow: 4px 0 30px var(--shadow);
  }
  .close-btn { display: flex; }
}
</style>
