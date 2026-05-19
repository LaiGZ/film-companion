<template>
  <div class="stats-grid">
    <div class="stat-card">
      <div class="stat-icon">🎞️</div>
      <div class="stat-value">{{ s?.film_count ?? '-' }}</div>
      <div class="stat-label">胶卷</div>
    </div>
    <div class="stat-card">
      <div class="stat-icon">📷</div>
      <div class="stat-value">{{ s?.gear_count ?? '-' }}</div>
      <div class="stat-label">设备</div>
    </div>
    <div class="stat-card">
      <div class="stat-icon">💰</div>
      <div class="stat-value">{{ s ? '¥' + s.total_value.toLocaleString() : '-' }}</div>
      <div class="stat-label">总价值</div>
    </div>
    <div class="stat-card" :class="{ 'has-warning': (s?.expired_count || 0) + (s?.expiring_count || 0) > 0 }">
      <div class="stat-icon">⚠️</div>
      <div class="stat-value">{{ s ? (s.expired_count + s.expiring_count) : '-' }}</div>
      <div class="stat-label">快过期/已过期</div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useDataStore } from '@/stores/dataStore'

const store = useDataStore()
const s = computed(() => store.stats)
</script>

<style scoped>
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px;
  margin-bottom: 20px;
}

.stat-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 18px;
  text-align: center;
  transition: all 0.2s;
}

.stat-card:hover {
  border-color: var(--primary);
}

.stat-card.has-warning {
  border-color: var(--warning);
}

.stat-icon { font-size: 24px; margin-bottom: 6px; }
.stat-value { font-size: 24px; font-weight: 700; }
.stat-label { font-size: 13px; color: var(--text2); margin-top: 2px; }

@media (max-width: 480px) {
  .stats-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>
