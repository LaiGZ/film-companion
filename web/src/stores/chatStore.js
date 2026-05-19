import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useChatStore = defineStore('chat', () => {
  const sessions = ref([])
  const currentSessionId = ref('')
  const messages = ref([])
  const isLoading = ref(false)
  const isStreaming = ref(false)
  const streamContent = ref('')
  const toolNames = ref([])

  const currentSession = computed(() =>
    sessions.value.find(s => s.id === currentSessionId.value)
  )

  const title = computed(() => {
    const s = currentSession.value
    return s?.title || s?.last_preview || '新会话'
  })

  return {
    sessions,
    currentSessionId,
    messages,
    isLoading,
    isStreaming,
    streamContent,
    toolNames,
    currentSession,
    title,
  }
})
