<template>
  <v-app>
    <v-app-bar color="primary" density="comfortable" elevation="2">
      <v-app-bar-title class="font-weight-bold">
        <v-icon icon="mdi-pulse" class="mr-2" />
        Web Alive Monitoring
      </v-app-bar-title>
      <template v-slot:append>
        <v-btn
          variant="text"
          class="mr-2 d-none d-sm-inline-flex"
          prepend-icon="mdi-shield-crown-outline"
          @click="handleAdminClick"
        >
          管理
        </v-btn>
        <v-menu>
          <template v-slot:activator="{ props }">
            <v-btn icon v-bind="props">
              <v-icon icon="mdi-account-circle" />
            </v-btn>
          </template>
          <v-list density="compact">
            <v-list-item>
              <v-list-item-title class="text-body-2">{{ auth.email }}</v-list-item-title>
            </v-list-item>
            <v-divider />
            <v-list-item @click="showDeleteDialog = true" prepend-icon="mdi-account-remove">
              <v-list-item-title class="text-error">アカウント削除</v-list-item-title>
            </v-list-item>
            <v-list-item @click="handleLogout" prepend-icon="mdi-logout">
              <v-list-item-title>ログアウト</v-list-item-title>
            </v-list-item>
          </v-list>
        </v-menu>
      </template>
    </v-app-bar>
    <v-main>
      <slot />
    </v-main>

    <!-- アカウント削除確認ダイアログ -->
    <v-dialog v-model="showDeleteDialog" max-width="440" persistent>
      <v-card>
        <v-card-title class="text-h6">
          <v-icon icon="mdi-alert" color="error" class="mr-2" />
          アカウント削除
        </v-card-title>
        <v-card-text>
          本当にアカウントを削除しますか？この操作は取り消せません。
        </v-card-text>
        <v-card-text v-if="deleteError">
          <v-alert type="error" variant="tonal" density="compact">
            {{ deleteError }}
          </v-alert>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="showDeleteDialog = false; deleteError = ''">
            キャンセル
          </v-btn>
          <v-btn color="error" variant="flat" :loading="deleteLoading" @click="handleDeleteAccount">
            削除する
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- 管理者認証ダイアログ -->
    <v-dialog v-model="showAdminDialog" max-width="400" persistent>
      <v-card>
        <v-card-title class="text-h6">管理者認証</v-card-title>
        <v-card-text>
          <v-alert v-if="adminError" type="error" variant="tonal" density="compact" class="mb-4">
            {{ adminError }}
          </v-alert>
          <v-form @submit.prevent="handleAdminAuth" ref="adminFormRef">
            <v-text-field
              v-model="adminId"
              label="ID"
              prepend-inner-icon="mdi-account"
              :rules="[(v: string) => !!v || 'IDを入力してください']"
              class="mb-2"
            />
            <v-text-field
              v-model="adminPassword"
              label="パスワード"
              type="password"
              prepend-inner-icon="mdi-lock"
              :rules="[(v: string) => !!v || 'パスワードを入力してください']"
            />
          </v-form>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="showAdminDialog = false; adminError = ''">
            キャンセル
          </v-btn>
          <v-btn color="primary" variant="flat" @click="handleAdminAuth">
            認証
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-app>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import api from '../services/api'

const auth = useAuthStore()
const router = useRouter()

const showDeleteDialog = ref(false)
const deleteLoading = ref(false)
const deleteError = ref('')

const showAdminDialog = ref(false)
const adminId = ref('')
const adminPassword = ref('')
const adminError = ref('')
const adminFormRef = ref()

async function handleLogout() {
  sessionStorage.removeItem('adminAuth')
  await auth.logout()
  router.push({ name: 'login' })
}

async function handleDeleteAccount() {
  try {
    deleteLoading.value = true
    deleteError.value = ''
    const response = await api.delete('/users/me')
    if (response.data?.success) {
      await auth.logout()
      router.push({ name: 'login' })
    } else {
      deleteError.value = response.data?.error || 'アカウント削除に失敗しました'
    }
  } catch (e: unknown) {
    if (e && typeof e === 'object' && 'response' in e) {
      const axiosError = e as { response?: { data?: { error?: string } } }
      deleteError.value = axiosError.response?.data?.error || 'アカウント削除に失敗しました'
    } else {
      deleteError.value = 'アカウント削除に失敗しました'
    }
  } finally {
    deleteLoading.value = false
  }
}

function handleAdminClick() {
  if (sessionStorage.getItem('adminAuth') === 'true') {
    router.push({ name: 'admin-users' })
    return
  }
  adminId.value = ''
  adminPassword.value = ''
  adminError.value = ''
  showAdminDialog.value = true
}

async function handleAdminAuth() {
  const { valid } = await adminFormRef.value.validate()
  if (!valid) return

  if (adminId.value === 'admin' && adminPassword.value === 'osasi034') {
    sessionStorage.setItem('adminAuth', 'true')
    showAdminDialog.value = false
    router.push({ name: 'admin-users' })
  } else {
    adminError.value = 'IDまたはパスワードが正しくありません'
  }
}
</script>
