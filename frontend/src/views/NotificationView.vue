<template>
  <AppLayout>
    <v-container class="py-6" fluid style="max-width: 960px">
      <v-breadcrumbs :items="breadcrumbs" class="px-0 mb-2">
        <template #divider>
          <v-icon icon="mdi-chevron-right" size="small" />
        </template>
      </v-breadcrumbs>

      <div class="d-flex align-center justify-space-between mb-6">
        <h1 class="text-h5 font-weight-bold">{{ site?.site_name }} - 通知設定</h1>
      </div>

      <v-card class="mb-6">
        <v-card-title class="d-flex align-center justify-space-between">
          <span>通知先一覧</span>
          <v-btn color="primary" prepend-icon="mdi-plus" @click="openAddDialog">
            通知先を追加
          </v-btn>
        </v-card-title>
        <v-divider />

        <v-list v-if="siteNotifications.length > 0" lines="two">
          <v-list-item
            v-for="notif in siteNotifications"
            :key="notif.notification_id"
          >
            <template #prepend>
              <v-icon
                :icon="notif.type === 'email' ? 'mdi-email' : 'mdi-message-text'"
                :color="notif.type === 'email' ? 'primary' : 'accent'"
                size="28"
                class="mr-2"
              />
            </template>

            <v-list-item-title class="font-weight-medium">
              {{ notif.destination }}
            </v-list-item-title>
            <v-list-item-subtitle>
              <v-chip
                :text="notif.type === 'email' ? 'メール' : 'Slack'"
                size="x-small"
                variant="tonal"
                :color="notif.type === 'email' ? 'primary' : 'accent'"
                class="mr-2"
              />
              <span v-if="notif.type === 'slack' && notif.mention">
                メンション: {{ notif.mention }}
              </span>
            </v-list-item-subtitle>

            <template #append>
              <v-switch
                :model-value="notif.enabled"
                color="success"
                hide-details
                density="compact"
                class="mr-4"
                @update:model-value="handleToggle(notif, $event as boolean)"
              />
              <v-btn icon="mdi-pencil" variant="text" size="small" class="mr-1" @click="openEditDialog(notif)" />
              <v-btn icon="mdi-delete" variant="text" size="small" color="error" @click="handleDeleteNotification(notif.notification_id)" />
            </template>
          </v-list-item>
        </v-list>

        <v-card-text v-else class="text-center py-8 text-medium-emphasis">
          <v-icon icon="mdi-bell-off-outline" size="48" class="mb-3" />
          <p>通知先が設定されていません</p>
        </v-card-text>
      </v-card>

      <v-card class="mb-6">
        <v-card-title>テスト通知</v-card-title>
        <v-divider />
        <v-card-text class="d-flex ga-4">
          <v-btn
            variant="outlined"
            color="primary"
            prepend-icon="mdi-email-fast-outline"
            :loading="testNotifyLoading"
            @click="handleTestNotify"
          >
            テスト通知を送信
          </v-btn>
        </v-card-text>
      </v-card>

      <v-btn
        variant="text"
        prepend-icon="mdi-arrow-left"
        :to="`/sites/${siteId}`"
      >
        サイト設定に戻る
      </v-btn>

      <v-dialog v-model="dialogOpen" max-width="560" persistent>
        <v-card>
          <v-card-title>{{ editingNotification ? '通知先を編集' : '通知先を追加' }}</v-card-title>
          <v-divider />
          <v-card-text>
            <v-radio-group v-model="form.type" inline class="mb-4">
              <v-radio label="メール" value="email" />
              <v-radio label="Slack" value="slack" />
            </v-radio-group>

            <template v-if="form.type === 'email'">
              <v-text-field
                v-model="form.destination"
                label="メールアドレス"
                placeholder="user@example.com"
                :rules="emailRules"
                prepend-inner-icon="mdi-email"
              />
            </template>

            <template v-else>
              <v-text-field
                v-model="form.destination"
                label="SSM Parameter名"
                placeholder="/web-alive/slack-webhook-url"
                hint="SSM Parameter StoreのSecureString名を入力"
                persistent-hint
                prepend-inner-icon="mdi-key"
                class="mb-4"
              />
              <v-text-field
                v-model="form.mention"
                label="メンション先"
                placeholder="@channel, @user"
                prepend-inner-icon="mdi-at"
              />
            </template>

            <v-textarea
              v-model="form.messageTemplate"
              label="メッセージテンプレート（任意）"
              rows="3"
              auto-grow
              class="mt-2"
            />
          </v-card-text>
          <v-divider />
          <v-card-actions class="pa-4">
            <v-spacer />
            <v-btn variant="text" @click="closeDialog">キャンセル</v-btn>
            <v-btn color="primary" variant="flat" :disabled="!isFormValid" :loading="saving" @click="handleSaveNotification">
              保存
            </v-btn>
          </v-card-actions>
        </v-card>
      </v-dialog>

      <v-snackbar v-model="snackbar" :timeout="3000" :color="snackbarColor">
        {{ snackbarText }}
      </v-snackbar>
    </v-container>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useSitesStore } from '../stores/sites'
import type { Notification } from '../data/mock-data'
import AppLayout from '../components/AppLayout.vue'

const route = useRoute()
const sitesStore = useSitesStore()

const siteId = computed(() => route.params.id as string)
const site = computed(() => sitesStore.getSiteById(siteId.value))
const siteNotifications = computed(() => sitesStore.getNotificationsBySiteId(siteId.value))

const breadcrumbs = computed(() => [
  { title: 'ダッシュボード', to: '/' },
  { title: site.value?.site_name ?? '', to: `/sites/${siteId.value}` },
  { title: '通知設定', disabled: true },
])

const dialogOpen = ref(false)
const editingNotification = ref<Notification | null>(null)
const snackbar = ref(false)
const snackbarText = ref('')
const snackbarColor = ref('success')
const saving = ref(false)
const testNotifyLoading = ref(false)

const form = ref({
  type: 'email' as 'email' | 'slack',
  destination: '',
  mention: '',
  messageTemplate: '',
})

const emailRules = [
  (v: string) => !!v || 'メールアドレスを入力してください',
  (v: string) => v.includes('@') || '有効なメールアドレスを入力してください',
]

const isFormValid = computed(() => {
  if (!form.value.destination) return false
  if (form.value.type === 'email' && !form.value.destination.includes('@')) return false
  return true
})

function openAddDialog() {
  editingNotification.value = null
  form.value = { type: 'email', destination: '', mention: '', messageTemplate: '' }
  dialogOpen.value = true
}

function openEditDialog(notif: Notification) {
  editingNotification.value = notif
  form.value = {
    type: notif.type,
    destination: notif.destination,
    mention: notif.mention,
    messageTemplate: notif.message_template,
  }
  dialogOpen.value = true
}

function closeDialog() {
  dialogOpen.value = false
  editingNotification.value = null
}

function showMessage(text: string, color: string = 'success') {
  snackbarText.value = text
  snackbarColor.value = color
  snackbar.value = true
}

async function handleSaveNotification() {
  saving.value = true
  const data = {
    type: form.value.type,
    destination: form.value.destination,
    mention: form.value.mention,
    message_template: form.value.messageTemplate,
    enabled: true,
  }

  if (editingNotification.value) {
    const result = await sitesStore.updateNotification(
      siteId.value,
      editingNotification.value.notification_id,
      data,
    )
    if (result) {
      showMessage('通知設定を更新しました')
    } else {
      showMessage('更新に失敗しました', 'error')
    }
  } else {
    const result = await sitesStore.createNotification(siteId.value, data)
    if (result) {
      showMessage('通知先を追加しました')
    } else {
      showMessage('追加に失敗しました', 'error')
    }
  }

  saving.value = false
  closeDialog()
}

async function handleToggle(notif: Notification, enabled: boolean) {
  await sitesStore.updateNotification(siteId.value, notif.notification_id, { enabled })
}

async function handleDeleteNotification(notificationId: string) {
  const result = await sitesStore.deleteNotification(siteId.value, notificationId)
  if (result) {
    showMessage('通知先を削除しました')
  } else {
    showMessage('削除に失敗しました', 'error')
  }
}

async function handleTestNotify() {
  testNotifyLoading.value = true
  try {
    await sitesStore.testNotify(siteId.value)
    showMessage('テスト通知を送信しました')
  } catch {
    showMessage('テスト通知の送信に失敗しました', 'error')
  } finally {
    testNotifyLoading.value = false
  }
}

onMounted(async () => {
  if (!site.value) {
    await sitesStore.fetchSites()
  }
  await sitesStore.fetchNotifications(siteId.value)
})
</script>
