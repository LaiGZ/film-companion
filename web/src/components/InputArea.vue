<template>
  <div class="input-area">
    <!-- 图片预览 -->
    <div v-if="images.length > 0" class="image-preview-bar">
      <div v-for="(img, i) in images" :key="i" class="image-preview-item">
        <img :src="img" class="preview-thumb" />
        <button class="remove-img" @click="removeImage(i)">✕</button>
      </div>
    </div>
    <div class="input-inner">
      <button class="img-btn" @click="fileInput.click()" title="上传图片" :disabled="store.isLoading">
        <span>🖼️</span>
      </button>
      <input
        ref="fileInput"
        type="file"
        accept="image/*"
        multiple
        style="display:none"
        @change="handleFileSelect"
      />
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
        :disabled="(!text.trim() && images.length === 0) || store.isLoading"
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
const images = ref([])
const fileInput = ref(null)

function handleSend() {
  const msg = text.value.trim()
  if ((!msg || store.isLoading) && images.value.length === 0) return
  text.value = ''
  const imgs = [...images.value]
  images.value = []
  sendMessage(msg, imgs)
}

function handleFileSelect(e) {
  const files = e.target.files
  if (!files.length) return
  for (const file of files) {
    if (!file.type.startsWith('image/')) continue
    const reader = new FileReader()
    reader.onload = (ev) => {
      images.value.push(ev.target.result)
    }
    reader.readAsDataURL(file)
  }
  // 重置 input 以便重复选择同一文件
  fileInput.value.value = ''
}

function removeImage(index) {
  images.value.splice(index, 1)
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
  padding: 0 24px 12px;
  padding-bottom: max(12px, env(safe-area-inset-bottom));
  background: var(--surface);
  flex-shrink: 0;
}

/* 图片预览条 */
.image-preview-bar {
  display: flex;
  gap: 8px;
  padding: 10px 0 6px;
  overflow-x: auto;
  max-width: 720px;
  margin: 0 auto;
}
.image-preview-item {
  position: relative;
  flex-shrink: 0;
}
.preview-thumb {
  width: 64px;
  height: 64px;
  object-fit: cover;
  border-radius: 8px;
  border: 1px solid var(--border);
}
.remove-img {
  position: absolute;
  top: -6px;
  right: -6px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: none;
  background: var(--danger, #ff3b30);
  color: white;
  font-size: 11px;
  line-height: 1;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
}

.input-inner {
  max-width: 720px;
  margin: 0 auto;
  display: flex;
  gap: 8px;
  align-items: flex-end;
}

.img-btn {
  background: none;
  border: 1px solid var(--border);
  color: var(--text2);
  width: 40px;
  height: 40px;
  border-radius: var(--radius-lg);
  font-size: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
  transition: all 0.2s;
}
.img-btn:hover { background: var(--surface2); color: var(--text); }
.img-btn:disabled { opacity: 0.4; cursor: not-allowed; }

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
  .input-area { padding: 0 12px 10px; }
}
</style>
