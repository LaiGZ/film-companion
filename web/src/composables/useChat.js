import { useAuth } from './useAuth'
import { useChatStore } from '@/stores/chatStore'
import { useSessions } from './useSessions'

export function useChat() {
  const { authFetch } = useAuth()
  const store = useChatStore()
  const { createSession, loadSessions, switchSession } = useSessions()

  async function sendMessage(text) {
    if (!text || store.isLoading) return

    // 确保有会话
    if (!store.currentSessionId) {
      await createSession()
      if (!store.currentSessionId) return
    }

    const sessionId = store.currentSessionId

    // 添加用户消息到本地
    store.messages.push({ role: 'user', content: text })
    store.isLoading = true
    store.isStreaming = true
    store.streamContent = ''
    store.toolNames = []

    try {
      const response = await authFetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, session_id: sessionId }),
      })

      if (!response.ok) {
        store.messages.push({ role: 'assistant', content: '❌ 出错了，请重试' })
        return
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let fullContent = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          let event
          try {
            event = JSON.parse(line.slice(6))
          } catch {
            continue
          }

          switch (event.type) {
            case 'token':
              fullContent += event.content
              store.streamContent = fullContent
              break
            case 'tool_start':
              store.toolNames = event.tools || []
              break
            case 'tool_result':
              // 工具完成
              break
            case 'done':
              store.messages.push({ role: 'assistant', content: fullContent })
              store.streamContent = ''
              store.isStreaming = false
              await loadSessions()
              break
            case 'error':
              store.messages.push({ role: 'assistant', content: '⚠️ ' + event.content })
              store.isStreaming = false
              break
          }
        }
      }
    } catch (err) {
      if (err.message !== 'unauthorized' && err.message !== 'auth_failed') {
        store.messages.push({ role: 'assistant', content: '❌ 网络错误: ' + err.message })
      }
    } finally {
      store.isLoading = false
      store.isStreaming = false
      store.toolNames = []
    }
  }

  return { sendMessage }
}
