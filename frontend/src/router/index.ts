import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/signup',
      name: 'signup',
      component: () => import('../views/SignupView.vue'),
      meta: { requiresAuth: false },
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('../views/LoginView.vue'),
      meta: { requiresAuth: false },
    },
    {
      path: '/',
      name: 'dashboard',
      component: () => import('../views/DashboardView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/sites/:id',
      name: 'site-edit',
      component: () => import('../views/SiteEditView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/sites/:id/notifications',
      name: 'site-notifications',
      component: () => import('../views/NotificationView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/sites/:id/history',
      name: 'site-history',
      component: () => import('../views/HistoryView.vue'),
      meta: { requiresAuth: true },
    },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()

  if (!auth.isAuthenticated) {
    await auth.checkAuth()
  }

  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return { name: 'login' }
  }
  if ((to.name === 'login' || to.name === 'signup') && auth.isAuthenticated) {
    return { name: 'dashboard' }
  }
})

export default router
