<template>
  <div class="message-area" ref="scrollRef">
    <div class="message-inner">
      <!-- 欢迎页（无消息时） -->
      <div v-if="store.messages.length === 0 && !store.isStreaming" class="welcome">
        <div class="welcome-icon">🎞️</div>
        <h2>欢迎使用胶片伴侣</h2>
        <p>你的 AI 胶片管理助手。<br />说人话就能管好胶卷和设备。</p>
        <div class="suggestions">
          <button class="suggestion-chip" @click="$emit('suggest', '买了3卷富士 Provia 100F')">📸 录入胶卷</button>
          <button class="suggestion-chip" @click="$emit('suggest', '我有哪些反转片？')">🔍 查库存</button>
          <button class="suggestion-chip" @click="$emit('suggest', '快过期的胶卷有哪些？')">⚠️ 过期提醒</button>
          <button class="suggestion-chip" @click="$emit('suggest', '我有哪些相机？')">📷 查设备</button>
        </div>
      </div>

      <!-- 消息列表 -->
      <div
        v-for="(msg, i) in store.messages"
        :key="i"
        class="message"
        :class="msg.role"
      >
        <div v-if="msg.role === 'assistant'" class="msg-avatar ai">🤖</div>
        <div class="msg-bubble" :class="msg.role">
          {{ msg.content }}
        </div>
        <div v-if="msg.role === 'user'" class="msg-avatar user">👤</div>
      </div>

      <!-- 工具调用指示 -->
      <div v-if="store.toolNames.length > 0" class="tool-indicator">
        <div class="tool-spinner"></div>
        <span>🔍 {{ store.toolNames.join(', ') }}</span>
      </div>

      <!-- 流式内容 -->
      <div v-if="store.isStreaming" class="message assistant">
        <div class="msg-avatar ai">🤖</div>
        <div class="msg-bubble assistant streaming">
          {{ store.streamContent }}<span class="cursor-blink"></span>
        </div>
      </div>

      <!-- 打字指示 -->
      <div v-if="store.isLoading && !store.isStreaming && store.toolNames.length === 0" class="typing-hint">
        <div class="typing-dots">
          <span></span><span></span><span></span>
        </div>
        <span>胶片伴侣正在思考...</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'
import { useChatStore } from '@/stores/chatStore'

defineEmits(['suggest'])

const store = useChatStore()
const scrollRef = ref(null)

// 自动滚动到底
watch(
  () => [store.messages.length, store.streamContent],
  async () => {
    await nextTick()
    if (scrollRef.value) {
      scrollRef.value.scrollTop = scrollRef.value.scrollHeight
    }
  },
  { deep: true }
)
</script>

<style scoped>
.message-area {
  flex: 1;
  overflow-y: auto;
  padding: 16px 0;
}

.message-inner {
  max-width: 720px;
  margin: 0 auto;
  padding: 0 24px;
}

/* 欢迎页 */
.welcome {
  text-align: center;
  padding: 60px 0 30px;
}
.welcome-icon { font-size: 56px; margin-bottom: 12px; }
.welcome h2 { font-size: 22px; margin-bottom: 6px; }
.welcome p { color: var(--text2); font-size: 14px; line-height: 1.6; max-width: 400px; margin: 0 auto; }
.suggestions { display: flex; gap: 8px; flex-wrap: wrap; justify-content: center; margin-top: 20px; }
.suggestion-chip {
  background: var(--surface2);
  border: 1px solid var(--border);
  color: var(--text2);
  padding: 8px 16px;
  border-radius: 20px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}
.suggestion-chip:hover {
  background: var(--user-bubble);
  color: var(--text);
  border-color: var(--primary);
}

/* 消息 */
.message {
  display: flex;
  gap: 10px;
  margin-bottom: 18px;
  animation: fadeIn 0.25s ease;
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}

.message.user { flex-direction: row-reverse; }

.msg-avatar {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 15px;
  flex-shrink: 0;
}
.msg-avatar.user { background: var(--user-bubble); }
.msg-avatar.ai { background: var(--primary); color: white; }

.msg-bubble {
  max-width: 72%;
  padding: 10px 14px;
  border-radius: var(--radius-lg);
  line-height: 1.6;
  font-size: 15px;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.msg-bubble.user {
  background: var(--user-bubble);
  border-bottom-right-radius: 4px;
}

.msg-bubble.assistant {
  background: var(--ai-bubble);
  border: 1px solid var(--border);
  border-bottom-left-radius: 4px;
}

.msg-bubble.streaming {
  border-color: var(--primary);
}

.cursor-blink {
  display: inline-block;
  width: 2px;
  height: 1em;
  background: var(--primary);
  margin-left: 2px;
  animation: blink 0.8s step-end infinite;
  vertical-align: text-bottom;
}
@keyframes blink {
  50% { opacity: 0; }
}

/* 工具指示 */
.tool-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0 10px 40px;
  color: var(--text2);
  font-size: 13px;
  animation: fadeIn 0.2s ease;
}
.tool-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid var(--border);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* 打字指示 */
.typing-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text2);
  font-size: 14px;
  margin-bottom: 18px;
  padding-left: 40px;
}
.typing-dots { display: flex; gap: 4px; }
.typing-dots span {
  width: 7px; height: 7px;
  background: var(--text3);
  border-radius: 50%;
  animation: bounce 1.4s infinite;
}
.typing-dots span:nth-child(2) { animation-delay: 0.2s; }
.typing-dots span:nth-child(3) { animation-delay: 0.4s; }
@keyframes bounce {
  0%, 60%, 100% { transform: translateY(0); }
  30% { transform: translateY(-5px); }
}

@media (max-width: 768px) {
  .message-inner { padding: 0 12px; }
  .msg-bubble { max-width: 88%; font-size: 14px; }
  .message.user .msg-bubble { max-width: 82%; }
  .welcome { padding: 40px 0 24px; }
}
</style>
