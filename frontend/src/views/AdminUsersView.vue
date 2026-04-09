<template>
  <AppLayout>
    <v-container class="py-6" fluid>
      <div class="d-flex align-center mb-6">
        <v-icon icon="mdi-shield-crown-outline" color="primary" size="28" class="mr-3" />
        <h1 class="text-h5 font-weight-bold">ユーザー管理</h1>
      </div>

      <v-alert v-if="errorMessage" type="error" variant="tonal" class="mb-4" closable @click:close="errorMessage = ''">
        {{ errorMessage }}
      </v-alert>

      <v-alert v-if="successMessage" type="success" variant="tonal" class="mb-4" closable @click:close="successMessage = ''">
        {{ successMessage }}
      </v-alert>

      <v-card elevation="1">
        <v-data-table
          :headers="headers"
          :items="users"
          :loading="loading"
          item-value="email"
          density="comfortable"
          hover
        >
          <template v-slot:item.enabled="{ item }">
            <v-chip
              :color="item.enabled ? 'success' : 'grey'"
              size="small"
              variant="tonal"
            >
              {{ item.enabled ? '有効' : '無効' }}
            </v-chip>
          </template>
          <template v-slot:item.actions="{ item }">
            <v-btn
              :icon="item.enabled ? 'mdi-account-off' : 'mdi-account-check'"
              size="small"
              variant="text"
              :color="item.enabled ? 'warning' : 'success'"
              :title="item.enabled ? '無効化' : '有効化'"
              @click="toggleStatus(item)"
              :loading="item._toggling"
            />
            <v-btn
              icon="mdi-lock-reset"
              size="small"
              variant="text"
              color="info"
              title="パスワードリセット"
              @click="resetPassword(item)"
              :loading="item._resetting"
            />
            <v-btn
              icon="mdi-delete"
              size="small"
              variant="text"
              color="error"
              title="削除"
              @click="confirmDelete(item)"
            />
          </template>
        </v-data-table>
      </v-card>

      <!-- 削除確認ダイアログ -->
      <v-dialog v-model="showDeleteDialog" max-width="440" persistent>
        <v-card>
          <v-card-title class="text-h6">
            <v-icon icon="mdi-alert" color="error" class="mr-2" />
            ユーザー削除
          </v-card-title>
          <v-card-text>
            <strong>{{ deleteTarget?.email }}</strong> を削除しますか？この操作は取り消せません。
          </v-card-text>
          <v-card-actions>
            <v-spacer />
            <v-btn variant="text" @click="showDeleteDialog = false">キャンセル</v-btn>
            <v-btn color="error" variant="flat" :loading="deleteLoading" @click="deleteUser">削除する</v-btn>
          </v-card-actions>
        </v-card>
      </v-dialog>
    </v-container>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import AppLayout from '../components/AppLayout.vue'
import api from '../services/api'

interface UserItem {
  email: string
  enabled: boolean
  status: string
  created_at: string
  _toggling?: boolean
  _resetting?: boolean
}

const router = useRouter()
const users = ref<UserItem[]>([])
const loading = ref(false)
const errorMessage = ref('')
const successMessage = ref('')
const showDeleteDialog = ref(false)
const deleteTarget = ref<UserItem | null>(null)
const deleteLoading = ref(false)

const headers = [
  { title: 'メールアドレス', key: 'email', sortable: true },
  { title: 'ステータス', key: 'enabled', sortable: true, width: '120px' },
  { title: '作成日時', key: 'created_at', sortable: true, width: '200px' },
  { title: '操作', key: 'actions', sortable: false, width: '160px' },
]

function getAdminAuthHeader(): Record<string, string> {
  const creds = btoa('admin:osasi034')
  return { 'X-Admin-Auth': creds }
}

onMounted(async () => {
  if (sessionStorage.getItem('adminAuth') !== 'true') {
    router.push({ name: 'dashboard' })
    return
  }
  await fetchUsers()
})

async function fetchUsers() {
  try {
    loading.value = true
    errorMessage.value = ''
    const response = await api.get('/admin/users', { headers: getAdminAuthHeader() })
    if (response.data?.success) {
      users.value = response.data.data.map((u: UserItem) => ({ ...u, _toggling: false, _resetting: false }))
    } else {
      errorMessage.value = response.data?.error || 'ユーザー一覧の取得に失敗しました'
    }
  } catch {
    errorMessage.value = 'ユーザー一覧の取得に失敗しました'
  } finally {
    loading.value = false
  }
}

async function toggleStatus(item: UserItem) {
  try {
    item._toggling = true
    errorMessage.value = ''
    const response = await api.post(
      `/admin/users/${encodeURIComponent(item.email)}/toggle-status`,
      null,
      { headers: getAdminAuthHeader() },
    )
    if (response.data?.success) {
      item.enabled = response.data.data.enabled
      successMessage.value = `${item.email} を${item.enabled ? '有効' : '無効'}にしました`
    } else {
      errorMessage.value = response.data?.error || 'ステータス変更に失敗しました'
    }
  } catch {
    errorMessage.value = 'ステータス変更に失敗しました'
  } finally {
    item._toggling = false
  }
}

async function resetPassword(item: UserItem) {
  try {
    item._resetting = true
    errorMessage.value = ''
    const response = await api.post(
      `/admin/users/${encodeURIComponent(item.email)}/reset-password`,
      null,
      { headers: getAdminAuthHeader() },
    )
    if (response.data?.success) {
      successMessage.value = `${item.email} にパスワードリセットメールを送信しました`
    } else {
      errorMessage.value = response.data?.error || 'パスワードリセットに失敗しました'
    }
  } catch {
    errorMessage.value = 'パスワードリセットに失敗しました'
  } finally {
    item._resetting = false
  }
}

function confirmDelete(item: UserItem) {
  deleteTarget.value = item
  showDeleteDialog.value = true
}

async function deleteUser() {
  if (!deleteTarget.value) return
  try {
    deleteLoading.value = true
    errorMessage.value = ''
    const response = await api.delete(
      `/admin/users/${encodeURIComponent(deleteTarget.value.email)}`,
      { headers: getAdminAuthHeader() },
    )
    if (response.data?.success) {
      successMessage.value = `${deleteTarget.value.email} を削除しました`
      users.value = users.value.filter(u => u.email !== deleteTarget.value?.email)
    } else {
      errorMessage.value = response.data?.error || 'ユーザー削除に失敗しました'
    }
  } catch {
    errorMessage.value = 'ユーザー削除に失敗しました'
  } finally {
    deleteLoading.value = false
    showDeleteDialog.value = false
  }
}
</script>
