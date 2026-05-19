import { createRouter, createWebHashHistory } from 'vue-router'
import ChatPage from '@/pages/ChatPage.vue'
import DataPage from '@/pages/DataPage.vue'

const routes = [
  {
    path: '/',
    name: 'chat',
    component: ChatPage,
  },
  {
    path: '/data',
    name: 'data',
    component: DataPage,
  },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

export default router
