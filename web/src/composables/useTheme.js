import { ref, watch } from 'vue'

const THEMES = [
  { id: 'minimal',  name: '极简白', icon: '💬' },
  { id: 'deepseek', name: '深空灰', icon: '🌌' },
  { id: 'warm',     name: '暖阳米', icon: '☀️' },
  { id: 'darkroom', name: '暗房红', icon: '🎞️' },
  { id: 'forest',   name: '墨绿',   icon: '🌲' },
]

const themeId = ref(localStorage.getItem('theme') || 'minimal')
const isDark = ref(localStorage.getItem('dark') === 'true')

function applyTheme() {
  document.body.className = `theme-${themeId.value}`
  if (isDark.value) document.body.classList.add('dark')
}

// 初始化
applyTheme()

export function useTheme() {
  function setTheme(id) {
    themeId.value = id
    localStorage.setItem('theme', id)
    applyTheme()
  }

  function toggleDark() {
    isDark.value = !isDark.value
    localStorage.setItem('dark', isDark.value ? 'true' : 'false')
    applyTheme()
  }

  // 跟随系统
  let mediaQuery = null
  function followSystem(shouldFollow) {
    if (shouldFollow) {
      mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
      isDark.value = mediaQuery.matches
      localStorage.setItem('dark', isDark.value ? 'true' : 'false')
      applyTheme()
      mediaQuery.addEventListener('change', (e) => {
        isDark.value = e.matches
        localStorage.setItem('dark', isDark.value ? 'true' : 'false')
        applyTheme()
      })
    } else {
      if (mediaQuery) {
        mediaQuery.removeEventListener('change', () => {})
        mediaQuery = null
      }
    }
  }

  return {
    themeId,
    isDark,
    THEMES,
    setTheme,
    toggleDark,
    followSystem,
  }
}
