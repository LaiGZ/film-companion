<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="store.showAuthModal" class="auth-overlay" @click.self="store.closeAuthModal()">
        <div class="auth-modal" @click.stop>
          <div class="auth-logo">🎞️</div>
          <h2 class="auth-title">{{ store.authModalMode === 'login' ? '胶片伴侣 AI' : '注册账号' }}</h2>

          <!-- 登录 -->
          <form v-if="store.authModalMode === 'login'" class="auth-form" @submit.prevent="handleLogin">
            <div class="auth-field">
              <input v-model="loginUsername" type="text" placeholder="用户名" autocomplete="username" />
            </div>
            <div class="auth-field">
              <input v-model="loginPassword" type="password" placeholder="密码" autocomplete="current-password" />
            </div>
            <p v-if="store.authError" class="auth-error">{{ store.authError }}</p>
            <button type="submit" class="auth-btn" :disabled="loading">
              {{ loading ? '登录中...' : '登 录' }}
            </button>
            <p class="auth-switch">
              还没有账号？
              <a @click="store.authModalMode = 'register'; store.authError = ''">立即注册</a>
            </p>
          </form>

          <!-- 注册 -->
          <form v-else class="auth-form" @submit.prevent="handleRegister">
            <div class="auth-field">
              <input v-model="regUsername" type="text" placeholder="用户名（2-32个字符）" autocomplete="off" />
            </div>
            <div class="auth-field">
              <input v-model="regPassword" type="password" placeholder="密码（至少6位）" autocomplete="new-password" />
            </div>
            <div class="auth-field">
              <input v-model="regConfirm" type="password" placeholder="确认密码" autocomplete="new-password" />
            </div>
            <p v-if="store.authError" class="auth-error">{{ store.authError }}</p>
            <button type="submit" class="auth-btn" :disabled="loading">
              {{ loading ? '注册中...' : '注 册' }}
            </button>
            <p class="auth-switch">
              <a @click="store.authModalMode = 'login'; store.authError = ''">← 返回登录</a>
            </p>
          </form>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref } from 'vue'
import { useAuthStore } from '@/stores/authStore'
import { useAuth } from '@/composables/useAuth'

const store = useAuthStore()
const { login, register } = useAuth()
const loading = ref(false)

const loginUsername = ref('')
const loginPassword = ref('')
const regUsername = ref('')
const regPassword = ref('')
const regConfirm = ref('')

async function handleLogin() {
  loading.value = true
  await login(loginUsername.value, loginPassword.value)
  loading.value = false
}

async function handleRegister() {
  loading.value = true
  await register(regUsername.value, regPassword.value, regConfirm.value)
  loading.value = false
}
</script>

<style scoped>
.auth-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.auth-modal {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 36px 32px 28px;
  width: 360px;
  max-width: 90vw;
  box-shadow: 0 20px 60px var(--shadow);
}

.auth-logo {
  text-align: center;
  font-size: 42px;
  margin-bottom: 4px;
}

.auth-title {
  text-align: center;
  font-size: 20px;
  font-weight: 600;
  margin-bottom: 24px;
  color: var(--text);
}

.auth-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.auth-field input {
  width: 100%;
  padding: 11px 14px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 10px;
  color: var(--text);
  font-size: 15px;
  outline: none;
  transition: border-color 0.2s;
}

.auth-field input:focus {
  border-color: var(--primary);
}

.auth-field input::placeholder {
  color: var(--text3);
}

.auth-error {
  color: var(--danger);
  font-size: 13px;
  text-align: center;
  min-height: 20px;
}

.auth-btn {
  width: 100%;
  padding: 11px;
  background: var(--primary);
  color: white;
  border: none;
  border-radius: 10px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.2s;
}

.auth-btn:hover { opacity: 0.9; }
.auth-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.auth-switch {
  text-align: center;
  font-size: 13px;
  color: var(--text2);
  margin-top: 4px;
}

.auth-switch a {
  color: var(--primary);
  cursor: pointer;
  font-weight: 500;
}

.auth-switch a:hover { text-decoration: underline; }

/* 过渡动画 */
.modal-enter-active, .modal-leave-active {
  transition: opacity 0.3s ease;
}
.modal-enter-active .auth-modal,
.modal-leave-active .auth-modal {
  transition: transform 0.3s ease, opacity 0.3s ease;
}
.modal-enter-from, .modal-leave-to {
  opacity: 0;
}
.modal-enter-from .auth-modal {
  transform: scale(0.95) translateY(10px);
}
.modal-leave-to .auth-modal {
  transform: scale(0.95) translateY(10px);
}
</style>
