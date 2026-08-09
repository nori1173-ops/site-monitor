import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  signIn,
  signUp,
  confirmSignUp,
  signOut,
  getCurrentUser,
  fetchAuthSession,
} from 'aws-amplify/auth'

export const useAuthStore = defineStore('auth', () => {
  const email = ref<string | null>(null)
  const isAuthenticated = computed(() => email.value !== null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function checkAuth(): Promise<boolean> {
    try {
      const user = await getCurrentUser()
      email.value = user.signInDetails?.loginId ?? user.username
      return true
    } catch {
      email.value = null
      return false
    }
  }

  async function login(userEmail: string, password: string): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const result = await signIn({ username: userEmail, password })
      if (result.isSignedIn) {
        email.value = userEmail
      } else {
        throw new Error('サインインが完了しませんでした。MFA等の追加ステップが必要です。')
      }
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : 'ログインに失敗しました'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function register(userEmail: string, password: string): Promise<void> {
    loading.value = true
    error.value = null
    try {
      await signUp({
        username: userEmail,
        password,
        options: {
          userAttributes: {
            email: userEmail,
          },
        },
      })
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : 'サインアップに失敗しました'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function confirmRegistration(userEmail: string, code: string): Promise<void> {
    loading.value = true
    error.value = null
    try {
      await confirmSignUp({
        username: userEmail,
        confirmationCode: code,
      })
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '確認コードの検証に失敗しました'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function logout(): Promise<void> {
    try {
      await signOut()
    } catch {
      // no-op
    }
    email.value = null
  }

  async function getIdToken(): Promise<string | null> {
    try {
      const session = await fetchAuthSession()
      return session.tokens?.idToken?.toString() ?? null
    } catch {
      return null
    }
  }

  return {
    email,
    isAuthenticated,
    loading,
    error,
    checkAuth,
    login,
    register,
    confirmRegistration,
    logout,
    getIdToken,
  }
})
