import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useAuthStore = defineStore('auth', () => {
  // ============ 状态 ============
  const accessToken = ref(localStorage.getItem('access_token') || '')
  const refreshToken = ref(localStorage.getItem('refresh_token') || '')
  const user = ref(JSON.parse(localStorage.getItem('user') || 'null'))
  const showAuthModal = ref(false)
  const authModalMode = ref('login') // 'login' | 'register'
  const authError = ref('')

  // ============ 计算属性 ============
  const isLoggedIn = computed(() => !!accessToken.value)
  const username = computed(() => user.value?.username || '')
  const userId = computed(() => user.value?.id || '')

  // ============ 方法 ============

  function _save() {
    if (accessToken.value) {
      localStorage.setItem('access_token', accessToken.value)
    } else {
      localStorage.removeItem('access_token')
    }
    if (refreshToken.value) {
      localStorage.setItem('refresh_token', refreshToken.value)
    } else {
      localStorage.removeItem('refresh_token')
    }
    if (user.value) {
      localStorage.setItem('user', JSON.stringify(user.value))
    } else {
      localStorage.removeItem('user')
    }
  }

  function setAuth(data) {
    accessToken.value = data.access_token
    refreshToken.value = data.refresh_token
    user.value = data.user
    _save()
    closeAuthModal()
  }

  function clearAuth() {
    accessToken.value = ''
    refreshToken.value = ''
    user.value = null
    _save()
  }

  function openAuthModal(mode = 'login') {
    authModalMode.value = mode
    authError.value = ''
    showAuthModal.value = true
  }

  function closeAuthModal() {
    showAuthModal.value = false
    authError.value = ''
  }

  return {
    accessToken,
    refreshToken,
    user,
    showAuthModal,
    authModalMode,
    authError,
    isLoggedIn,
    username,
    userId,
    setAuth,
    clearAuth,
    openAuthModal,
    closeAuthModal,
  }
})
