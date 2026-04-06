<template>
  <AppLayout>
    <v-container class="py-6" fluid style="max-width: 900px">
      <v-btn variant="text" prepend-icon="mdi-arrow-left" @click="router.push('/')" class="mb-4">
        ダッシュボードに戻る
      </v-btn>

      <h1 class="text-h5 font-weight-bold mb-6">
        {{ isEditMode ? 'サイト編集' : 'サイト新規登録' }}
      </h1>

      <v-form ref="formRef" v-model="formValid" @submit.prevent="handleSave">
        <!-- セクション1: 基本情報 -->
        <v-card class="mb-6 pa-6" border>
          <div class="text-subtitle-1 font-weight-bold mb-4">
            <v-icon icon="mdi-information-outline" class="mr-1" />
            基本情報
          </div>

          <v-text-field
            v-model="form.site_name"
            label="現場名"
            :rules="[rules.required]"
            class="mb-4"
          />

          <div class="text-body-2 text-medium-emphasis mb-2">監視種別</div>
          <v-row class="mb-4">
            <v-col cols="6">
              <v-card
                :color="form.monitor_type === 'url_check' ? 'primary' : undefined"
                :variant="form.monitor_type === 'url_check' ? 'flat' : 'outlined'"
                class="pa-4 text-center cursor-pointer"
                @click="form.monitor_type = 'url_check'"
              >
                <v-icon
                  icon="mdi-web"
                  size="36"
                  :color="form.monitor_type === 'url_check' ? 'white' : 'primary'"
                  class="mb-2"
                />
                <div :class="form.monitor_type === 'url_check' ? 'text-white' : ''">
                  URL更新チェック
                </div>
              </v-card>
            </v-col>
            <v-col cols="6">
              <v-card
                :color="form.monitor_type === 'cloudwatch_log' ? 'primary' : undefined"
                :variant="form.monitor_type === 'cloudwatch_log' ? 'flat' : 'outlined'"
                class="pa-4 text-center cursor-pointer"
                @click="form.monitor_type = 'cloudwatch_log'"
              >
                <v-icon
                  icon="mdi-cloud-search"
                  size="36"
                  :color="form.monitor_type === 'cloudwatch_log' ? 'white' : 'primary'"
                  class="mb-2"
                />
                <div :class="form.monitor_type === 'cloudwatch_log' ? 'text-white' : ''">
                  CloudWatchログ検索
                </div>
              </v-card>
            </v-col>
          </v-row>

          <!-- URL更新チェック -->
          <div v-if="form.monitor_type === 'url_check'">
            <div class="text-body-2 text-medium-emphasis mb-2">監視対象URL一覧</div>
            <div v-for="(target, index) in urlTargets" :key="index" class="d-flex align-center mb-2">
              <v-text-field
                v-model="target.url"
                :label="`URL ${index + 1}`"
                :rules="[rules.required, rules.url]"
                hide-details="auto"
                density="compact"
                class="flex-grow-1"
              />
              <v-btn
                icon="mdi-close"
                variant="text"
                color="error"
                size="small"
                class="ml-2"
                :disabled="urlTargets.length <= 1"
                @click="removeUrlTarget(index)"
              />
            </div>
            <v-btn
              variant="tonal"
              color="primary"
              size="small"
              prepend-icon="mdi-plus"
              class="mt-2"
              @click="addUrlTarget"
            >
              URLを追加
            </v-btn>
          </div>

          <!-- CloudWatchログ検索 -->
          <div v-if="form.monitor_type === 'cloudwatch_log'">
            <v-select
              v-model="cwForm.log_group"
              :items="logGroupOptions"
              label="ロググループ"
              :rules="[rules.required]"
              class="mb-2"
            />
            <v-text-field
              v-model="cwForm.message_filter"
              label="messageフィルタ"
              class="mb-2"
            />
            <v-text-field
              v-model="cwForm.json_search_word"
              label="JSON検索ワード"
              class="mb-2"
            />
            <v-text-field
              v-model.number="cwForm.search_period_minutes"
              label="検索期間（分）"
              type="number"
              :rules="[rules.required, rules.positiveNumber]"
              class="mb-2"
            />
            <v-btn
              variant="tonal"
              color="secondary"
              prepend-icon="mdi-magnify"
              @click="showCwTestResult = true"
            >
              テスト検索
            </v-btn>
            <v-alert
              v-if="showCwTestResult"
              type="info"
              variant="tonal"
              class="mt-3"
              closable
              @click:close="showCwTestResult = false"
            >
              <div class="font-weight-bold">テスト検索結果</div>
              <div>ヒット件数: 42件</div>
              <div>最終ヒット: 2026-04-06 09:45:00</div>
            </v-alert>
          </div>
        </v-card>

        <!-- セクション2: 監視スケジュール -->
        <v-card class="mb-6 pa-6" border>
          <div class="text-subtitle-1 font-weight-bold mb-4">
            <v-icon icon="mdi-clock-outline" class="mr-1" />
            監視スケジュール
          </div>

          <v-row>
            <v-col cols="12" sm="6">
              <v-text-field
                v-model="form.schedule_start"
                label="監視開始時刻"
                type="time"
                :rules="[rules.required]"
              />
            </v-col>
            <v-col cols="12" sm="6">
              <v-select
                v-model="form.schedule_interval_minutes"
                :items="intervalOptions"
                item-title="label"
                item-value="value"
                label="監視間隔"
                :rules="[rules.required]"
              />
            </v-col>
          </v-row>

          <v-text-field
            v-model.number="form.consecutive_threshold"
            label="連続欠測閾値"
            type="number"
            :rules="[rules.required, rules.positiveNumber]"
            :hint="`${form.consecutive_threshold}回連続で更新なしの場合に通知します`"
            persistent-hint
            class="mb-2"
          />

          <v-switch
            v-model="form.enabled"
            label="監視を有効にする"
            color="primary"
            hide-details
          />
        </v-card>

        <!-- セクション3: 通知設定 -->
        <v-card class="mb-6 pa-6" border>
          <div class="text-subtitle-1 font-weight-bold mb-4">
            <v-icon icon="mdi-bell-outline" class="mr-1" />
            通知設定
          </div>

          <v-alert type="info" variant="tonal" class="mb-4">
            詳細な通知設定（メール・Slack）は別画面で行います。
          </v-alert>

          <v-btn
            variant="outlined"
            color="primary"
            prepend-icon="mdi-bell-cog-outline"
            :disabled="!isEditMode"
            @click="router.push(`/sites/${route.params.id}/notifications`)"
          >
            通知設定を編集
          </v-btn>
          <div v-if="!isEditMode" class="text-caption text-medium-emphasis mt-1">
            サイト登録後に通知設定を編集できます
          </div>
        </v-card>

        <!-- メタ情報（編集時のみ） -->
        <v-card v-if="isEditMode && existingSite" class="mb-6 pa-6" border>
          <div class="text-subtitle-1 font-weight-bold mb-4">
            <v-icon icon="mdi-account-outline" class="mr-1" />
            メタ情報
          </div>
          <v-row dense>
            <v-col cols="12" sm="4">
              <div class="text-caption text-medium-emphasis">登録者</div>
              <div class="text-body-2">{{ existingSite.created_by }}</div>
            </v-col>
            <v-col cols="12" sm="4">
              <div class="text-caption text-medium-emphasis">最終更新者</div>
              <div class="text-body-2">{{ existingSite.updated_by }}</div>
            </v-col>
            <v-col cols="12" sm="4">
              <div class="text-caption text-medium-emphasis">更新日時</div>
              <div class="text-body-2">{{ formatDateTime(existingSite.updated_at) }}</div>
            </v-col>
          </v-row>
        </v-card>

        <!-- テストチェック実行 -->
        <v-card class="mb-6 pa-6" border>
          <v-btn
            variant="outlined"
            color="secondary"
            prepend-icon="mdi-play-circle-outline"
            @click="handleTestCheck"
          >
            テストチェック実行
          </v-btn>
        </v-card>

        <!-- アクションボタン -->
        <div class="d-flex ga-3">
          <v-btn type="submit" color="primary" size="large" :disabled="!formValid">
            保存
          </v-btn>
          <v-btn variant="outlined" size="large" @click="router.push('/')">
            キャンセル
          </v-btn>
          <v-spacer />
          <v-btn
            v-if="isEditMode"
            color="error"
            variant="outlined"
            size="large"
            prepend-icon="mdi-delete"
            @click="showDeleteDialog = true"
          >
            削除
          </v-btn>
        </div>
      </v-form>

      <!-- 削除確認ダイアログ -->
      <v-dialog v-model="showDeleteDialog" max-width="400">
        <v-card class="pa-6">
          <v-card-title class="text-h6 pa-0 mb-4">サイトを削除しますか？</v-card-title>
          <v-card-text class="pa-0 mb-6">
            「{{ form.site_name }}」を削除します。この操作は取り消せません。
          </v-card-text>
          <v-card-actions class="pa-0">
            <v-spacer />
            <v-btn variant="text" @click="showDeleteDialog = false">キャンセル</v-btn>
            <v-btn color="error" variant="flat" @click="handleDelete">削除する</v-btn>
          </v-card-actions>
        </v-card>
      </v-dialog>

      <!-- テストチェック結果ダイアログ -->
      <v-dialog v-model="showTestDialog" max-width="600">
        <v-card class="pa-6">
          <v-card-title class="text-h6 pa-0 mb-4">テストチェック結果</v-card-title>
          <v-card-text class="pa-0 mb-4">
            <div v-if="form.monitor_type === 'url_check'">
              <v-table density="compact">
                <thead>
                  <tr>
                    <th>URL</th>
                    <th>状態</th>
                    <th>Last-Modified</th>
                    <th>ETag</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(target, i) in urlTargets" :key="i">
                    <td class="text-caption">{{ target.url || '(未入力)' }}</td>
                    <td>
                      <v-chip
                        :color="i % 2 === 0 ? 'success' : 'warning'"
                        size="small"
                        label
                      >
                        {{ i % 2 === 0 ? 'updated' : 'not_updated' }}
                      </v-chip>
                    </td>
                    <td class="text-caption">{{ i % 2 === 0 ? '2026-04-06T09:00:00' : '-' }}</td>
                    <td class="text-caption">{{ i % 2 === 0 ? '"abc123"' : '-' }}</td>
                  </tr>
                </tbody>
              </v-table>
            </div>
            <div v-else>
              <div class="mb-2"><strong>ヒット件数:</strong> 42件</div>
              <div><strong>最終ヒット日時:</strong> 2026-04-06 09:45:00</div>
            </div>
          </v-card-text>
          <v-card-actions class="pa-0">
            <v-spacer />
            <v-btn variant="text" @click="showTestDialog = false">閉じる</v-btn>
          </v-card-actions>
        </v-card>
      </v-dialog>
    </v-container>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useSitesStore } from '../stores/sites'
import AppLayout from '../components/AppLayout.vue'
import type { Site, UrlTarget, CloudWatchLogTarget } from '../data/mock-data'

const router = useRouter()
const route = useRoute()
const sitesStore = useSitesStore()

const formValid = ref(false)
const showDeleteDialog = ref(false)
const showTestDialog = ref(false)
const showCwTestResult = ref(false)

const isEditMode = computed(() => route.params.id !== 'new')
const existingSite = computed(() =>
  isEditMode.value ? sitesStore.getSiteById(route.params.id as string) : undefined,
)

const logGroupOptions = [
  'DataTransferSystem2-OsBoard-Function1',
  'NetMAIL-Backend-Subscriber',
  'NetMAIL-Backend-Worker',
  'NetMAIL-Backend-Publisher',
]

const intervalOptions = [
  { label: '5分', value: 5 },
  { label: '10分', value: 10 },
  { label: '15分', value: 15 },
  { label: '30分', value: 30 },
  { label: '1時間', value: 60 },
  { label: '3時間', value: 180 },
  { label: '6時間', value: 360 },
  { label: '12時間', value: 720 },
  { label: '24時間', value: 1440 },
]

const rules = {
  required: (v: unknown) => !!v || v === 0 || '必須項目です',
  url: (v: string) => !v || /^https?:\/\/.+/.test(v) || '有効なURLを入力してください',
  positiveNumber: (v: number) => (Number.isFinite(v) && v > 0) || '1以上の数値を入力してください',
}

const form = reactive({
  site_name: '',
  monitor_type: 'url_check' as 'url_check' | 'cloudwatch_log',
  schedule_start: '00:00',
  schedule_interval_minutes: 60,
  consecutive_threshold: 3,
  enabled: true,
})

const urlTargets = ref<{ url: string }[]>([{ url: '' }])

const cwForm = reactive<CloudWatchLogTarget>({
  log_group: '',
  message_filter: '',
  json_search_word: '',
  search_period_minutes: 60,
})

function addUrlTarget() {
  urlTargets.value = [...urlTargets.value, { url: '' }]
}

function removeUrlTarget(index: number) {
  urlTargets.value = urlTargets.value.filter((_, i) => i !== index)
}

function formatDateTime(iso: string): string {
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

function buildTargets(): Site['targets'] {
  if (form.monitor_type === 'url_check') {
    return urlTargets.value.map((t) => ({ url: t.url }) as UrlTarget)
  }
  return [{ ...cwForm } as CloudWatchLogTarget]
}

function handleSave() {
  const now = new Date().toISOString()
  const targets = buildTargets()

  if (isEditMode.value) {
    sitesStore.updateSite(route.params.id as string, {
      site_name: form.site_name,
      monitor_type: form.monitor_type,
      targets,
      schedule_start: form.schedule_start,
      schedule_interval_minutes: form.schedule_interval_minutes,
      consecutive_threshold: form.consecutive_threshold,
      enabled: form.enabled,
      updated_by: 'miyaji@osasi.co.jp',
      updated_at: now,
    })
  } else {
    const newSite: Site = {
      site_id: `site-${String(Date.now()).slice(-6)}`,
      site_name: form.site_name,
      monitor_type: form.monitor_type,
      targets,
      schedule_start: form.schedule_start,
      schedule_interval_minutes: form.schedule_interval_minutes,
      consecutive_threshold: form.consecutive_threshold,
      enabled: form.enabled,
      last_check_status: 'updated',
      last_checked_at: now,
      consecutive_miss_count: 0,
      created_by: 'miyaji@osasi.co.jp',
      updated_by: 'miyaji@osasi.co.jp',
      created_at: now,
      updated_at: now,
    }
    sitesStore.addSite(newSite)
  }
  router.push('/')
}

function handleDelete() {
  sitesStore.deleteSite(route.params.id as string)
  showDeleteDialog.value = false
  router.push('/')
}

function handleTestCheck() {
  showTestDialog.value = true
}

function isUrlTarget(t: unknown): t is UrlTarget {
  return typeof t === 'object' && t !== null && 'url' in t
}

function isCwTarget(t: unknown): t is CloudWatchLogTarget {
  return typeof t === 'object' && t !== null && 'log_group' in t
}

onMounted(() => {
  if (isEditMode.value && existingSite.value) {
    const site = existingSite.value
    form.site_name = site.site_name
    form.monitor_type = site.monitor_type
    form.schedule_start = site.schedule_start
    form.schedule_interval_minutes = site.schedule_interval_minutes
    form.consecutive_threshold = site.consecutive_threshold
    form.enabled = site.enabled

    if (site.monitor_type === 'url_check') {
      urlTargets.value = site.targets
        .filter(isUrlTarget)
        .map((t) => ({ url: t.url }))
      if (urlTargets.value.length === 0) {
        urlTargets.value = [{ url: '' }]
      }
    } else {
      const target = site.targets.find(isCwTarget)
      if (target) {
        cwForm.log_group = target.log_group
        cwForm.message_filter = target.message_filter
        cwForm.json_search_word = target.json_search_word
        cwForm.search_period_minutes = target.search_period_minutes
      }
    }
  }
})
</script>

<style scoped>
.cursor-pointer {
  cursor: pointer;
}
</style>
