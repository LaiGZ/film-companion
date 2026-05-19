<template>
  <div class="filter-bar">
    <div class="tabs">
      <button
        class="tab"
        :class="{ active: store.activeTab === 'film' }"
        @click="switchTab('film')"
      >🎞️ 胶卷</button>
      <button
        class="tab"
        :class="{ active: store.activeTab === 'gear' }"
        @click="switchTab('gear')"
      >📷 设备</button>
    </div>
    <div class="filters">
      <select v-model="statusVal" class="filter-select" @change="load">
        <option value="">全部状态</option>
        <option v-for="s in statusOptions" :key="s" :value="s">{{ s }}</option>
      </select>
      <select v-model="typeVal" class="filter-select" @change="load">
        <option value="">全部类型</option>
        <option v-for="t in typeOptions" :key="t" :value="t">{{ t }}</option>
      </select>
      <button class="refresh-btn" @click="load">🔄</button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useDataStore } from '@/stores/dataStore'

const store = useDataStore()

const filmStatuses = ['未使用', '已拍摄', '已冲洗', '已扫描', '已使用']
const gearStatuses = ['在用', '闲置', '待出', '已出', '维修中']
const filmTypes = ['彩色反转片', '彩色负片', '黑白负片', '电影卷']
const gearTypes = ['相机', '镜头', '三脚架', '闪光灯', '滤镜', '扫描仪', '其他']

const statusOptions = computed(() =>
  store.activeTab === 'film' ? filmStatuses : gearStatuses
)
const typeOptions = computed(() =>
  store.activeTab === 'film' ? filmTypes : gearTypes
)

const statusVal = ref('')
const typeVal = ref('')

function switchTab(tab) {
  store.activeTab = tab
  statusVal.value = ''
  typeVal.value = ''
  load()
}

function load() {
  if (store.activeTab === 'film') {
    store.filmFilter = { status: statusVal.value, film_type: typeVal.value }
  } else {
    store.gearFilter = { status: statusVal.value, gear_type: typeVal.value }
  }
  // 触发 data page 的加载
  window.dispatchEvent(new CustomEvent('data-refresh'))
}

// 监听刷新事件
import { onMounted, onUnmounted } from 'vue'
onMounted(() => window.addEventListener('data-refresh', doLoad))
onUnmounted(() => window.removeEventListener('data-refresh', doLoad))

async function doLoad() {
  const { useAuth } = await import('@/composables/useAuth')
  const { authFetch } = useAuth()
  try {
    const params = new URLSearchParams({ sort: 'created_at', order: 'DESC', limit: '500' })
    if (store.activeTab === 'film') {
      const f = store.filmFilter
      if (f.status) params.set('status', f.status)
      if (f.film_type) params.set('film_type', f.film_type)
      const res = await authFetch(`/api/film?${params}`)
      const data = await res.json()
      if (data.status === 'ok') store.films = data.films
    } else {
      const f = store.gearFilter
      if (f.status) params.set('status', f.status)
      if (f.gear_type) params.set('gear_type', f.gear_type)
      const res = await authFetch(`/api/gear?${params}`)
      const data = await res.json()
      if (data.status === 'ok') store.gear = data.gear
    }
  } catch {}
}
</script>

<style scoped>
.filter-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.tabs {
  display: flex;
  gap: 0;
  border-bottom: 2px solid var(--border);
}

.tab {
  padding: 8px 20px;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  color: var(--text2);
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
  font-family: inherit;
}

.tab:hover { color: var(--text); }
.tab.active {
  color: var(--primary);
  border-bottom-color: var(--primary);
  font-weight: 600;
}

.filters {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

.filter-select {
  padding: 6px 10px;
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  color: var(--text);
  font-size: 13px;
  font-family: inherit;
  outline: none;
  cursor: pointer;
}

.filter-select:focus {
  border-color: var(--primary);
}

.refresh-btn {
  padding: 6px 14px;
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  color: var(--text2);
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
  font-family: inherit;
}

.refresh-btn:hover {
  background: var(--primary);
  color: white;
  border-color: var(--primary);
}
</style>
