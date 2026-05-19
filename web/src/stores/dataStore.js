import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useDataStore = defineStore('data', () => {
  const films = ref([])
  const gear = ref([])
  const stats = ref(null)
  const activeTab = ref('film') // 'film' | 'gear'
  const filmFilter = ref({ status: '', film_type: '' })
  const gearFilter = ref({ status: '', gear_type: '' })

  return {
    films,
    gear,
    stats,
    activeTab,
    filmFilter,
    gearFilter,
  }
})
