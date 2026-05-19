<template>
  <div class="app-root">
    <!-- 登录弹窗 -->
    <AuthModal />

    <!-- 路由视图 -->
    <router-view v-if="ready" />
    <div v-else class="loading-screen">
      <div class="loading-spinner"></div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/authStore'
import { useTheme } from '@/composables/useTheme'
import AuthModal from '@/components/AuthModal.vue'

const store = useAuthStore()
const { followSystem } = useTheme()
const ready = ref(false)

onMounted(() => {
  // 应用已保存的主题
  followSystem(false)

  // 如果未登录，弹出登录框
  if (!store.isLoggedIn) {
    store.openAuthModal('login')
  }

  ready.value = true
})
</script>

<style scoped>
.app-root {
  height: 100%;
  display: flex;
  flex-direction: column;
}
.loading-screen {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}
.loading-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--border);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
