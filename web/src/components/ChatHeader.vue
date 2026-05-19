<template>
  <header class="chat-header">
    <div class="header-left">
      <button class="menu-btn" @click="$emit('toggleSidebar')">☰</button>
      <span class="logo">🎞️</span>
      <span class="header-title">{{ title }}</span>
    </div>
    <div class="header-right">
      <span v-if="store.isLoggedIn" class="user-name">{{ store.username }}</span>
      <button class="icon-btn" @click="showThemePanel = !showThemePanel" title="主题">🎨</button>
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
      <router-link to="/data" class="icon-btn" title="数据">📊</router-link>
      <button v-if="store.isLoggedIn" class="icon-btn logout-btn" @click="handleLogout" title="退出">🚪</button>
    </div>
  </header>
</template>

<script setup>
import { ref } from 'vue'
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

const title = ref('胶片伴侣 AI')

// 监听会话标题变化
import { watch } from 'vue'
watch(() => chatStore.currentSession, (s) => {
  title.value = s?.title || s?.last_preview
    ? (s.title || s.last_preview).slice(0, 28) + ((s.title || s.last_preview).length > 28 ? '...' : '')
    : '胶片伴侣 AI'
}, { immediate: true })

async function handleLogout() {
  showThemePanel.value = false
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

.user-name {
  font-size: 13px;
  color: var(--text2);
  margin-right: 4px;
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

.logout-btn:hover { color: var(--danger); }

/* 主题面板 */
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
  .user-name { display: none; }
}
</style>
