import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useAuthStore = defineStore('auth', () => {
  const email = ref<string | null>(localStorage.getItem('auth_email'))
  const isAuthenticated = computed(() => email.value !== null)

  function login(userEmail: string) {
    email.value = userEmail
    localStorage.setItem('auth_email', userEmail)
  }

  function logout() {
    email.value = null
    localStorage.removeItem('auth_email')
  }

  return { email, isAuthenticated, login, logout }
})
