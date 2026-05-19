<template>
  <div class="input-area">
    <div class="input-inner">
      <textarea
        v-model="text"
        class="input-box"
        :placeholder="store.isLoading ? '正在回复...' : '记录胶卷、查库存、问问题...'"
        :disabled="store.isLoading"
        rows="1"
        @keydown="handleKeydown"
        @input="autoResize"
      ></textarea>
      <button
        class="send-btn"
        :disabled="!text.trim() || store.isLoading"
        @click="handleSend"
      >
        <span v-if="store.isLoading" class="send-spinner"></span>
        <span v-else>🚀</span>
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useChatStore } from '@/stores/chatStore'
import { useChat } from '@/composables/useChat'

const store = useChatStore()
const { sendMessage } = useChat()
const text = ref('')

function handleSend() {
  const msg = text.value.trim()
  if (!msg || store.isLoading) return
  text.value = ''
  sendMessage(msg)
}

function handleKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

function autoResize(e) {
  const el = e.target
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 160) + 'px'
}
</script>

<style scoped>
.input-area {
  border-top: 1px solid var(--border);
  padding: 12px 24px;
  padding-bottom: max(12px, env(safe-area-inset-bottom));
  background: var(--surface);
  flex-shrink: 0;
}

.input-inner {
  max-width: 720px;
  margin: 0 auto;
  display: flex;
  gap: 10px;
  align-items: flex-end;
}

.input-box {
  flex: 1;
  padding: 10px 14px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  color: var(--text);
  font-size: 15px;
  font-family: inherit;
  outline: none;
  resize: none;
  line-height: 1.5;
  max-height: 160px;
  transition: border-color 0.2s;
}

.input-box:focus {
  border-color: var(--primary);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--primary) 15%, transparent);
}

.input-box::placeholder {
  color: var(--text3);
}

.input-box:disabled {
  opacity: 0.6;
}

.send-btn {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: none;
  background: var(--primary);
  color: white;
  font-size: 18px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all 0.2s;
}

.send-btn:hover:not(:disabled) {
  opacity: 0.9;
  transform: scale(1.05);
}

.send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.send-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

@media (max-width: 768px) {
  .input-area { padding: 10px 12px; }
}
</style>
