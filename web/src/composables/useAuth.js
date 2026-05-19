/**
 * useAuth — 全局 fetch 拦截器 + 无感刷新
 *
 * - 自动注入 Authorization: Bearer header
 * - 401 时自动尝试 refresh_token
 * - 刷新失败 / 单点登录被踢 → 弹出登录框
 */

import { useAuthStore } from '@/stores/authStore'

let _refreshing = null

function parseJwt(token) {
  try {
    return JSON.parse(atob(token.split('.')[1]))
  } catch {
    return null
  }
}

export function useAuth() {
  const store = useAuthStore()

  async function login(username, password) {
    store.authError = ''
    if (!username || !password) {
      store.authError = '请输入用户名和密码'
      return false
    }
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      })
      const data = await res.json()
      if (data.status !== 'ok') {
        store.authError = data.detail || '登录失败'
        return false
      }
      store.setAuth(data)
      return true
    } catch {
      store.authError = '网络错误，请重试'
      return false
    }
  }

  async function register(username, password, confirm) {
    store.authError = ''
    if (!username || !password) {
      store.authError = '请输入用户名和密码'
      return false
    }
    if (password.length < 6) {
      store.authError = '密码至少 6 位'
      return false
    }
    if (password !== confirm) {
      store.authError = '两次密码不一致'
      return false
    }
    try {
      const res = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      })
      const data = await res.json()
      if (data.status !== 'ok') {
        store.authError = data.detail || '注册失败'
        return false
      }
      store.setAuth(data)
      return true
    } catch {
      store.authError = '网络错误，请重试'
      return false
    }
  }

  async function logout() {
    try {
      await fetch('/api/auth/logout', {
        method: 'POST',
        headers: { Authorization: 'Bearer ' + store.accessToken },
      })
    } catch { /* ignore */ }
    store.clearAuth()
    store.openAuthModal('login')
    store.authError = '已退出登录'
  }

  /**
   * 确保 access_token 有效，必要时自动刷新
   * 返回有效的 token，或 null (需要重新登录)
   */
  async function ensureToken() {
    const token = store.accessToken
    if (!token) {
      store.openAuthModal('login')
      return null
    }

    // 检查是否即将过期 (<1分钟)
    const payload = parseJwt(token)
    if (payload && payload.exp * 1000 > Date.now() + 60000) {
      return token
    }

    // 需要刷新
    if (!_refreshing) {
      _refreshing = (async () => {
        const rt = store.refreshToken
        if (!rt) throw new Error('no_rt')

        const res = await fetch('/api/auth/refresh', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: rt }),
        })

        if (!res.ok) {
          const data = await res.json().catch(() => ({}))
          store.clearAuth()
          store.openAuthModal('login')
          store.authError = data.detail || '登录已失效，请重新登录'
          throw new Error('refresh_fail')
        }

        const data = await res.json()
        store.accessToken = data.access_token
        localStorage.setItem('access_token', data.access_token)
      })()
    }

    try {
      await _refreshing
      return store.accessToken
    } finally {
      _refreshing = null
    }
  }

  /**
   * 带认证的 fetch — 自动注入 Bearer + 401 处理
   */
  async function authFetch(url, opts = {}) {
    // 认证相关 API 不处理
    if (url.includes('/api/auth/login') ||
        url.includes('/api/auth/register') ||
        url.includes('/api/auth/refresh')) {
      return fetch(url, opts)
    }

    opts = opts || {}
    opts.headers = opts.headers || {}

    try {
      const token = await ensureToken()
      if (token) {
        opts.headers = { ...opts.headers, Authorization: 'Bearer ' + token }
      }
    } catch {
      throw new Error('auth_failed')
    }

    const res = await fetch(url, opts)

    if (res.status === 401) {
      const data = await res.json().catch(() => ({}))
      store.clearAuth()
      store.openAuthModal('login')
      store.authError = data.detail || '登录已过期'
      throw new Error('unauthorized')
    }

    return res
  }

  return {
    login,
    register,
    logout,
    ensureToken,
    authFetch,
  }
}
