<template>
  <header class="chat-header">
    <div class="header-left">
      <button class="menu-btn" @click="$emit('toggleSidebar')">☰</button>
      <span class="logo">🎞️</span>
      <span class="header-title">{{ title }}</span>
    </div>
    <div class="header-right" ref="headerActions">
      <button v-if="store.isLoggedIn" class="icon-btn" @click="showUserPanel = !showUserPanel; showThemePanel = false" title="用户">
        <span class="user-icon">👤</span>
      </button>
      <!-- 用户面板 -->
      <Transition name="pop">
        <div v-if="showUserPanel" class="dropdown-panel">
          <p class="panel-title">{{ store.username }}</p>
          <router-link to="/data" class="panel-item" @click="showUserPanel = false">📊 数据管理</router-link>
          <div class="panel-divider"></div>
          <button class="panel-item panel-logout" @click="handleLogout">🚪 退出登录</button>
        </div>
      </Transition>
      <button class="icon-btn" @click="showThemePanel = !showThemePanel; showUserPanel = false" title="主题">🎨</button>
      <!-- 主题面板 -->
      <Transition name="pop">
        <div v-if="showThemePanel" class="theme-panel">
          <p class="theme-panel-title">主题</p>
          <div
            v-for="t in theme.THEMES"
            :key="t.id"
            class="theme-option"
            :class="{ active: theme.themeId.value === t.id }"
            @click="theme.setTheme(t.id); showThemePanel = false"
          >
            {{ t.icon }} {{ t.name }}
          </div>
          <div class="theme-divider"></div>
          <label class="theme-toggle">
            <input type="checkbox" :checked="theme.isDark.value" @change="theme.toggleDark()" />
            <span>暗色模式</span>
          </label>
        </div>
      </Transition>
    </div>
  </header>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { useAuthStore } from '@/stores/authStore'
import { useAuth } from '@/composables/useAuth'
import { useTheme } from '@/composables/useTheme'
import { useChatStore } from '@/stores/chatStore'

defineEmits(['toggleSidebar'])

const store = useAuthStore()
const chatStore = useChatStore()
const { logout } = useAuth()
const theme = useTheme()
const showThemePanel = ref(false)
const showUserPanel = ref(false)

const title = ref('胶片伴侣 AI')

const headerActions = ref(null)

function onDocumentClick(e) {
  if (!showThemePanel.value && !showUserPanel.value) return
  if (headerActions.value && !headerActions.value.contains(e.target)) {
    showThemePanel.value = false
    showUserPanel.value = false
  }
}

onMounted(() => document.addEventListener('click', onDocumentClick))
onUnmounted(() => document.removeEventListener('click', onDocumentClick))

// 监听会话标题变化
watch(() => chatStore.currentSession, (s) => {
  title.value = s?.title || s?.last_preview
    ? (s.title || s.last_preview).slice(0, 28) + ((s.title || s.last_preview).length > 28 ? '...' : '')
    : '胶片伴侣 AI'
}, { immediate: true })

async function handleLogout() {
  showThemePanel.value = false
  showUserPanel.value = false
  await logout()
}
</script>

<style scoped>
.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  height: 52px;
  border-bottom: 1px solid var(--border);
  background: var(--surface);
  flex-shrink: 0;
  z-index: 10;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 4px;
  position: relative;
}

.menu-btn {
  background: none;
  border: 1px solid var(--border);
  color: var(--text2);
  width: 34px;
  height: 34px;
  border-radius: var(--radius);
  font-size: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s;
}
.menu-btn:hover { background: var(--surface2); color: var(--text); }

.logo { font-size: 22px; }

.header-title {
  font-size: 15px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.icon-btn {
  background: none;
  border: 1px solid transparent;
  color: var(--text2);
  width: 34px;
  height: 34px;
  border-radius: var(--radius);
  font-size: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  text-decoration: none;
  transition: all 0.2s;
}
.icon-btn:hover { background: var(--surface2); color: var(--text); }

/* 用户／主题通用下拉面板 */
.dropdown-panel,
.theme-panel {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 4px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 8px;
  min-width: 150px;
  box-shadow: 0 8px 30px var(--shadow);
  z-index: 100;
}
.panel-title {
  font-size: 12px;
  color: var(--text2);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  padding: 4px 8px 6px;
  font-weight: 600;
}
.panel-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s;
  color: var(--text);
  text-decoration: none;
  border: none;
  background: none;
  width: 100%;
  text-align: left;
  box-sizing: border-box;
}
.panel-item:hover { background: var(--surface2); }
.panel-logout { color: var(--danger); }
.panel-logout:hover { background: var(--danger-bg, rgba(255,59,48,0.08)); }
.panel-divider {
  height: 1px;
  background: var(--border);
  margin: 4px 0;
}

/* 主题面板（保持独立样式） */
.theme-panel {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 4px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 12px;
  width: 180px;
  box-shadow: 0 8px 30px var(--shadow);
  z-index: 100;
}

.theme-panel-title {
  font-size: 12px;
  color: var(--text2);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 6px;
  font-weight: 600;
}

.theme-option {
  padding: 6px 8px;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s;
  color: var(--text);
}
.theme-option:hover { background: var(--surface2); }
.theme-option.active { background: var(--surface2); color: var(--primary); font-weight: 600; }

.theme-divider {
  height: 1px;
  background: var(--border);
  margin: 8px 0;
}

.theme-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 6px;
}
.theme-toggle:hover { background: var(--surface2); }

/* pop 过渡 */
.pop-enter-active, .pop-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.pop-enter-from, .pop-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

@media (max-width: 768px) {
  .chat-header { padding: 8px 12px; }
}
</style>
