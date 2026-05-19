import { useAuth } from './useAuth'
import { useChatStore } from '@/stores/chatStore'

export function useSessions() {
  const { authFetch } = useAuth()
  const store = useChatStore()

  async function loadSessions() {
    try {
      const res = await authFetch('/api/sessions?limit=50')
      const data = await res.json()
      if (data.status === 'ok') {
        store.sessions = data.sessions
      }
    } catch { /* 静默处理 */ }
  }

  async function createSession() {
    try {
      const res = await authFetch('/api/sessions', { method: 'POST' })
      const data = await res.json()
      store.currentSessionId = data.session_id
      store.messages = []
      await loadSessions()
    } catch { /* 静默处理 */ }
  }

  async function loadSessionMessages(sessionId) {
    try {
      const res = await authFetch(`/api/sessions/${sessionId}`)
      const data = await res.json()
      if (data.status === 'ok') {
        store.messages = (data.messages || []).filter(
          m => m.role === 'user' || m.role === 'assistant'
        )
      }
    } catch { /* 静默处理 */ }
  }

  async function switchSession(sessionId) {
    store.currentSessionId = sessionId
    store.messages = []
    store.streamContent = ''
    await loadSessionMessages(sessionId)
  }

  async function deleteSession(sessionId) {
    try {
      await authFetch(`/api/sessions/${sessionId}`, { method: 'DELETE' })
      if (store.currentSessionId === sessionId) {
        store.currentSessionId = ''
        store.messages = []
      }
      await loadSessions()
    } catch { /* 静默处理 */ }
  }

  return {
    loadSessions,
    createSession,
    loadSessionMessages,
    switchSession,
    deleteSession,
  }
}
