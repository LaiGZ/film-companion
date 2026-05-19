<template>
  <div>
    <table v-if="data.length > 0" class="data-table">
      <thead>
        <tr>
          <th v-for="col in columns" :key="col.key" @click="toggleSort(col.key)">
            {{ col.label }}
            <span v-if="sortKey === col.key" class="sort-icon">{{ sortDir === 'ASC' ? '↑' : '↓' }}</span>
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in sortedData" :key="row.id">
          <td v-for="col in columns" :key="col.key">
            <template v-if="col.key === 'expiry_status'">
              <span v-if="row.expiry_date && row.expiry_status === 'expired'" class="badge badge-danger">已过期</span>
              <span v-else-if="row.expiry_date && row.expiry_status === 'expiring'" class="badge badge-warning">即将到期</span>
              <span v-else-if="row.expiry_date" class="badge badge-ok">{{ row.days_left }}天</span>
              <span v-else>-</span>
            </template>
            <template v-else-if="col.key === 'status'">
              <span v-if="type === 'film'" :class="statusClass(row.status)">{{ row.status }}</span>
              <span v-else :class="gearStatusClass(row.status)">{{ row.status }}</span>
            </template>
            <template v-else-if="col.key === 'price' || col.key === 'purchase_price'">
              {{ row[col.key] ? '¥' + row[col.key] : '-' }}
            </template>
            <template v-else-if="col.key === 'meta'">
              <span class="meta-text">{{ formatMeta(row.meta) }}</span>
            </template>
            <template v-else>
              {{ row[col.key] ?? '-' }}
            </template>
          </td>
        </tr>
      </tbody>
    </table>
    <div v-else class="empty-state">
      <div class="empty-icon">{{ type === 'film' ? '🎞️' : '📷' }}</div>
      <p>还没有{{ type === 'film' ? '胶卷' : '设备' }}记录</p>
    </div>
    <div v-if="data.length > 0" class="table-footer">
      共 {{ data.length }} 条记录
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  data: { type: Array, default: () => [] },
  type: { type: String, default: 'film' }, // 'film' | 'gear'
})

const sortKey = ref('created_at')
const sortDir = ref('DESC')

const filmColumns = [
  { key: 'name', label: '型号' },
  { key: 'film_type', label: '类型' },
  { key: 'iso', label: 'ISO' },
  { key: 'format', label: '格式' },
  { key: 'quantity', label: '数量' },
  { key: 'status', label: '状态' },
  { key: 'expiry_date', label: '到期日' },
  { key: 'expiry_status', label: '状态' },
  { key: 'price', label: '价格' },
  { key: 'storage_location', label: '存放' },
  { key: 'meta', label: '备注' },
]

const gearColumns = [
  { key: 'name', label: '名称' },
  { key: 'gear_type', label: '类型' },
  { key: 'brand', label: '品牌' },
  { key: 'model', label: '型号' },
  { key: 'status', label: '状态' },
  { key: 'condition', label: '成色' },
  { key: 'price', label: '价格' },
  { key: 'purchase_date', label: '购买日期' },
  { key: 'storage_location', label: '存放' },
  { key: 'meta', label: '备注' },
]

const columns = computed(() => props.type === 'film' ? filmColumns : gearColumns)

const sortedData = computed(() => {
  const arr = [...props.data]
  const key = sortKey.value
  arr.sort((a, b) => {
    const va = a[key] ?? ''
    const vb = b[key] ?? ''
    let cmp = 0
    if (typeof va === 'number' && typeof vb === 'number') {
      cmp = va - vb
    } else {
      cmp = String(va).localeCompare(String(vb), 'zh-CN')
    }
    return sortDir.value === 'ASC' ? cmp : -cmp
  })
  return arr
})

function toggleSort(key) {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === 'ASC' ? 'DESC' : 'ASC'
  } else {
    sortKey.value = key
    sortDir.value = 'ASC'
  }
}

function statusClass(s) {
  const map = {
    '未使用': 'badge badge-ok',
    '已拍摄': 'badge badge-info',
    '已冲洗': 'badge badge-warning',
    '已扫描': 'badge badge-ok',
    '已使用': 'badge badge-inactive',
  }
  return map[s] || 'badge badge-inactive'
}

function gearStatusClass(s) {
  const map = {
    '在用': 'badge badge-ok',
    '闲置': 'badge badge-warning',
    '待出': 'badge badge-info',
    '已出': 'badge badge-inactive',
    '维修中': 'badge badge-danger',
  }
  return map[s] || 'badge badge-inactive'
}

function formatMeta(meta) {
  if (!meta || typeof meta !== 'object') return '-'
  return Object.entries(meta).map(([k, v]) => `${k}: ${v}`).join(', ').slice(0, 40)
}
</script>

<style scoped>
.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}

th {
  background: var(--surface2);
  padding: 10px 14px;
  text-align: left;
  font-weight: 600;
  white-space: nowrap;
  cursor: pointer;
  user-select: none;
  position: sticky;
  top: 0;
  z-index: 1;
}

th:hover {
  background: color-mix(in srgb, var(--surface2) 90%, var(--primary));
}

.sort-icon {
  margin-left: 4px;
  color: var(--primary);
}

td {
  padding: 8px 14px;
  border-top: 1px solid var(--border);
  white-space: nowrap;
}

tr:hover td {
  background: color-mix(in srgb, var(--surface) 98%, var(--primary));
}

.badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
}

.badge-ok { background: color-mix(in srgb, var(--success) 15%, transparent); color: var(--success); }
.badge-warning { background: color-mix(in srgb, var(--warning) 15%, transparent); color: var(--warning); }
.badge-danger { background: color-mix(in srgb, var(--danger) 15%, transparent); color: var(--danger); }
.badge-info { background: color-mix(in srgb, #4fc3f7 15%, transparent); color: #4fc3f7; }
.badge-inactive { background: color-mix(in srgb, var(--text3) 15%, transparent); color: var(--text3); }

.meta-text {
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  display: inline-block;
  vertical-align: middle;
  color: var(--text2);
  font-size: 13px;
}

.empty-state {
  text-align: center;
  padding: 60px 20px;
  color: var(--text2);
}

.empty-icon { font-size: 48px; margin-bottom: 12px; }

.table-footer {
  padding: 10px 14px;
  font-size: 13px;
  color: var(--text2);
  border-top: 1px solid var(--border);
}

@media (max-width: 768px) {
  th, td { padding: 6px 10px; font-size: 13px; }
}
</style>
