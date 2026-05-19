<template>
  <div class="data-page">
    <!-- 顶栏 -->
    <header class="data-header">
      <div class="header-left">
        <router-link to="/" class="back-btn">← 返回</router-link>
        <span class="logo">🎞️</span>
        <span class="header-title">胶片伴侣</span>
      </div>
    </header>

    <div class="data-content">
      <!-- 统计卡片 -->
      <StatsCards />

      <!-- Tab + 筛选 -->
      <FilterBar />

      <!-- 表格 -->
      <div class="table-wrap">
        <DataTable v-if="store.activeTab === 'film'" :data="store.films" type="film" />
        <DataTable v-else :data="store.gear" type="gear" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useAuthStore } from '@/stores/authStore'
import { useDataStore } from '@/stores/dataStore'
import { useAuth } from '@/composables/useAuth'
import StatsCards from '@/components/StatsCards.vue'
import FilterBar from '@/components/FilterBar.vue'
import DataTable from '@/components/DataTable.vue'

const store = useDataStore()
const { authFetch } = useAuth()

onMounted(async () => {
  await loadStats()
  await loadTableData()
})

async function loadStats() {
  try {
    const res = await authFetch('/api/stats')
    const data = await res.json()
    if (data.status === 'ok') store.stats = data.stats
  } catch {}
}

async function loadTableData() {
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

// 暴露刷新方法给子组件
defineExpose({ loadStats, loadTableData })
</script>

<style scoped>
.data-page {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.data-header {
  display: flex;
  align-items: center;
  padding: 8px 16px;
  height: 52px;
  border-bottom: 1px solid var(--border);
  background: var(--surface);
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.back-btn {
  color: var(--text2);
  text-decoration: none;
  font-size: 14px;
  padding: 4px 10px;
  border-radius: var(--radius);
  transition: all 0.2s;
}
.back-btn:hover { background: var(--surface2); color: var(--text); }

.logo { font-size: 22px; }
.header-title { font-size: 15px; font-weight: 600; }

.data-content {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
  max-width: 1200px;
  width: 100%;
  margin: 0 auto;
}

.table-wrap {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  overflow-x: auto;
}

@media (max-width: 768px) {
  .data-content { padding: 16px; }
}
</style>
