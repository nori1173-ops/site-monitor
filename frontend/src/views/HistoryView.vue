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

      <v-card>
        <v-tabs v-model="activeTab" color="primary">
          <v-tab value="check-history">
            <v-icon icon="mdi-format-list-checks" class="mr-2" />
            チェック履歴
          </v-tab>
          <v-tab value="status-changes">
            <v-icon icon="mdi-swap-horizontal" class="mr-2" />
            状態変化履歴
          </v-tab>
        </v-tabs>

        <v-divider />

        <v-tabs-window v-model="activeTab">
          <v-tabs-window-item value="check-history">
            <v-data-table
              :headers="checkHeaders"
              :items="sortedCheckResults"
              :items-per-page="5"
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
              <template #no-data>
                <div class="text-center py-8 text-medium-emphasis">
                  <v-icon icon="mdi-clipboard-text-off-outline" size="48" class="mb-3" />
                  <p>チェック履歴はまだありません</p>
                </div>
              </template>
            </v-data-table>
          </v-tabs-window-item>

          <v-tabs-window-item value="status-changes">
            <div v-if="sortedStatusChanges.length === 0" class="text-center py-12 text-medium-emphasis">
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
                <v-card variant="tonal" class="pa-3">
                  <div class="text-caption text-medium-emphasis mb-1">
                    {{ formatDateTime(change.changed_at) }}
                  </div>
                  <div class="font-weight-medium mb-1">
                    {{ translateStatus(change.previous_status) }} → {{ translateStatus(change.new_status) }}
                  </div>
                  <div class="text-caption text-medium-emphasis">
                    <v-icon icon="mdi-link-variant" size="14" class="mr-1" />
                    {{ change.trigger_url }}
                  </div>
                </v-card>
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

onMounted(async () => {
  if (!sitesStore.getSiteById(siteId.value)) {
    await sitesStore.fetchSites()
  }
  await sitesStore.fetchCheckResults(siteId.value)
  await sitesStore.fetchStatusChanges(siteId.value)
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
