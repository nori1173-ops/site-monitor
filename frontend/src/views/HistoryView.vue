<template>
  <AppLayout>
    <v-container class="py-6" fluid style="max-width: 960px">
      <v-breadcrumbs :items="breadcrumbs" class="px-0 mb-2">
        <template #divider>
          <v-icon icon="mdi-chevron-right" size="small" />
        </template>
      </v-breadcrumbs>

      <div class="d-flex align-center ga-4 mb-6">
        <h1 class="text-h5 font-weight-bold">{{ site?.site_name }} - 履歴</h1>
        <v-chip
          v-if="site"
          :color="statusColor"
          :text="statusLabel"
          variant="flat"
          size="small"
          class="font-weight-medium"
        />
      </div>

      <v-progress-linear v-if="loading" indeterminate color="primary" class="mb-2" />

      <v-card>
        <v-tabs v-model="activeTab" color="primary">
          <v-tab value="check-history">
            <v-icon icon="mdi-format-list-checks" class="mr-2" />
            チェック履歴
            <v-badge
              v-if="sortedCheckResults.length > 0"
              :content="sortedCheckResults.length"
              color="primary"
              inline
              class="ml-2"
            />
          </v-tab>
          <v-tab value="status-changes">
            <v-icon icon="mdi-swap-horizontal" class="mr-2" />
            状態変化履歴
            <v-badge
              v-if="sortedStatusChanges.length > 0"
              :content="sortedStatusChanges.length"
              color="primary"
              inline
              class="ml-2"
            />
          </v-tab>
        </v-tabs>

        <v-divider />

        <v-tabs-window v-model="activeTab">
          <v-tabs-window-item value="check-history">
            <div v-if="loading" class="pa-4">
              <v-skeleton-loader v-for="i in 3" :key="i" type="table-row" class="mb-2" />
            </div>
            <v-data-table
              v-else
              :headers="checkHeaders"
              :items="sortedCheckResults"
              :items-per-page="10"
              :items-per-page-options="[5, 10, 25, 50]"
              class="elevation-0"
            >
              <template #item.checked_at="{ value }">
                {{ formatDateTime(value) }}
              </template>
              <template #item.status="{ value }">
                <v-chip
                  :color="getStatusColor(value)"
                  :text="getStatusLabel(value)"
                  size="small"
                  variant="flat"
                />
              </template>
              <template #item.consecutive_miss_count="{ value }">
                <span :class="value > 0 ? 'text-error font-weight-bold' : ''">
                  {{ value }}
                </span>
              </template>
              <template #no-data>
                <div class="text-center py-8 text-medium-emphasis">
                  <v-icon icon="mdi-clipboard-text-off-outline" size="48" class="mb-3" />
                  <p>チェック履歴はまだありません</p>
                </div>
              </template>
            </v-data-table>
          </v-tabs-window-item>

          <v-tabs-window-item value="status-changes">
            <div v-if="loading" class="pa-4">
              <v-skeleton-loader v-for="i in 3" :key="i" type="list-item-three-line" class="mb-2" />
            </div>

            <div v-else-if="sortedStatusChanges.length === 0" class="text-center py-12 text-medium-emphasis">
              <v-icon icon="mdi-timeline-clock-outline" size="48" class="mb-3" />
              <p>状態変化の履歴はまだありません</p>
            </div>

            <v-timeline
              v-else
              side="end"
              density="compact"
              class="pa-4"
            >
              <v-timeline-item
                v-for="(change, idx) in sortedStatusChanges"
                :key="idx"
                :dot-color="getTimelineColor(change)"
                :icon="getTimelineIcon(change)"
                size="small"
              >
                <transition name="slide" appear>
                  <v-card variant="tonal" class="pa-3 timeline-card">
                    <div class="d-flex align-center justify-space-between mb-1">
                      <div class="text-caption text-medium-emphasis">
                        {{ formatDateTime(change.changed_at) }}
                      </div>
                      <div v-if="idx > 0" class="text-caption text-disabled">
                        {{ getTimeDiff(sortedStatusChanges[idx - 1].changed_at, change.changed_at) }}
                      </div>
                    </div>
                    <div class="d-flex align-center ga-2 mb-1">
                      <v-chip
                        :color="getStatusColor(change.previous_status)"
                        :text="translateStatus(change.previous_status)"
                        size="x-small"
                        variant="flat"
                      />
                      <v-icon icon="mdi-arrow-right" size="16" />
                      <v-chip
                        :color="getStatusColor(change.new_status)"
                        :text="translateStatus(change.new_status)"
                        size="x-small"
                        variant="flat"
                      />
                    </div>
                    <div class="text-caption text-medium-emphasis">
                      <v-icon icon="mdi-link-variant" size="14" class="mr-1" />
                      {{ change.trigger_url }}
                    </div>
                  </v-card>
                </transition>
              </v-timeline-item>
            </v-timeline>
          </v-tabs-window-item>
        </v-tabs-window>
      </v-card>

      <v-btn
        variant="text"
        prepend-icon="mdi-arrow-left"
        :to="`/sites/${siteId}`"
        class="mt-6"
      >
        サイト詳細に戻る
      </v-btn>
    </v-container>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useSitesStore } from '../stores/sites'
import type { StatusChange } from '../data/mock-data'
import AppLayout from '../components/AppLayout.vue'

const route = useRoute()
const sitesStore = useSitesStore()
const loading = ref(true)

onMounted(async () => {
  try {
    if (!sitesStore.getSiteById(siteId.value)) {
      await sitesStore.fetchSites()
    }
    await Promise.all([
      sitesStore.fetchCheckResults(siteId.value),
      sitesStore.fetchStatusChanges(siteId.value),
    ])
  } finally {
    loading.value = false
  }
})

const siteId = computed(() => route.params.id as string)
const site = computed(() => sitesStore.getSiteById(siteId.value))

const activeTab = ref('check-history')

const breadcrumbs = computed(() => [
  { title: 'ダッシュボード', to: '/' },
  { title: site.value?.site_name ?? '', to: `/sites/${siteId.value}` },
  { title: '履歴', disabled: true },
])

const statusColor = computed(() => {
  if (!site.value) return 'grey'
  if (site.value.last_check_status === 'updated') return 'success'
  if (site.value.last_check_status === 'error') return 'warning'
  return 'error'
})

const statusLabel = computed(() => {
  if (!site.value) return ''
  if (site.value.last_check_status === 'updated') return '正常'
  if (site.value.last_check_status === 'error') return 'エラー'
  return '欠測中'
})

const checkHeaders = [
  { title: 'チェック日時', key: 'checked_at', sortable: true },
  { title: '対象URL', key: 'target_url', sortable: false },
  { title: 'ステータス', key: 'status', sortable: true },
  { title: '連続欠測回数', key: 'consecutive_miss_count', sortable: true, align: 'end' as const },
]

const sortedCheckResults = computed(() =>
  [...sitesStore.getCheckResultsBySiteId(siteId.value)]
    .sort((a, b) => new Date(b.checked_at).getTime() - new Date(a.checked_at).getTime()),
)

const sortedStatusChanges = computed(() =>
  [...sitesStore.getStatusChangesBySiteId(siteId.value)]
    .sort((a, b) => new Date(b.changed_at).getTime() - new Date(a.changed_at).getTime()),
)

function formatDateTime(isoString: string): string {
  const date = new Date(isoString)
  return date.toLocaleString('ja-JP', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function getTimeDiff(olderIso: string, newerIso: string): string {
  const diff = new Date(olderIso).getTime() - new Date(newerIso).getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 60) return `${minutes}分後`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}時間後`
  const days = Math.floor(hours / 24)
  return `${days}日後`
}

function getStatusColor(status: string): string {
  if (status === 'updated') return 'success'
  if (status === 'error') return 'warning'
  return 'error'
}

function getStatusLabel(status: string): string {
  if (status === 'updated') return '正常'
  if (status === 'error') return 'エラー'
  return '欠測'
}

function translateStatus(status: string): string {
  if (status === 'updated') return '正常'
  if (status === 'not_updated') return '異常'
  if (status === 'error') return 'エラー'
  return status
}

function getTimelineColor(change: StatusChange): string {
  if (change.new_status === 'updated') return 'success'
  if (change.new_status === 'error') return 'warning'
  return 'error'
}

function getTimelineIcon(change: StatusChange): string {
  if (change.new_status === 'updated') return 'mdi-check-circle'
  if (change.new_status === 'error') return 'mdi-alert'
  return 'mdi-alert-circle'
}
</script>

<style scoped>
.timeline-card {
  transition: transform 0.2s ease;
}
.timeline-card:hover {
  transform: translateX(4px);
}
.slide-enter-active {
  transition: all 0.3s ease;
}
.slide-enter-from {
  opacity: 0;
  transform: translateX(-20px);
}
</style>
