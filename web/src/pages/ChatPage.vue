<template>
  <div class="chat-layout">
    <!-- 顶栏 -->
    <ChatHeader @toggle-sidebar="sidebarOpen = !sidebarOpen" />

    <div class="chat-body">
      <!-- 侧栏 -->
      <Transition name="sidebar">
        <Sidebar v-if="sidebarOpen" @close="sidebarOpen = false" />
      </Transition>

      <!-- 聊天主区域 -->
      <div class="chat-main" @click="sidebarOpen = false">
        <!-- 消息列表 -->
        <MessageList />

        <!-- 输入区 -->
        <InputArea />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/authStore'
import { useSessions } from '@/composables/useSessions'
import ChatHeader from '@/components/ChatHeader.vue'
import Sidebar from '@/components/Sidebar.vue'
import MessageList from '@/components/MessageList.vue'
import InputArea from '@/components/InputArea.vue'

const store = useAuthStore()
const { loadSessions, createSession } = useSessions()
const sidebarOpen = ref(window.innerWidth > 768)

onMounted(async () => {
  if (store.isLoggedIn) {
    await loadSessions()
    // 自动恢复或创建会话
    if (store.sessions.length > 0) {
      const { switchSession } = useSessions()
      await switchSession(store.sessions[0].id)
    } else {
      await createSession()
    }
  }
})
</script>

<style scoped>
.chat-layout {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.chat-body {
  flex: 1;
  display: flex;
  overflow: hidden;
  position: relative;
}

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
}

/* 侧栏过渡 */
.sidebar-enter-active,
.sidebar-leave-active {
  transition: transform 0.25s ease, opacity 0.25s ease;
}
.sidebar-enter-from,
.sidebar-leave-to {
  transform: translateX(-100%);
  opacity: 0;
}

@media (max-width: 768px) {
  .chat-body {
    position: relative;
  }
}
</style>
