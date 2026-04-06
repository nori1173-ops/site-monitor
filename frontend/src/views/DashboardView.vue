<template>
  <AppLayout>
    <v-container class="py-6" fluid style="max-width: 1200px">
      <v-progress-linear
        v-if="sitesStore.loading"
        indeterminate
        color="primary"
        class="mb-2"
      />

      <SummaryCards v-if="!sitesStore.loading" class="mb-6" />
      <div v-else class="mb-6">
        <v-row>
          <v-col v-for="i in 4" :key="i" cols="6" md="3">
            <v-skeleton-loader type="card" />
          </v-col>
        </v-row>
      </div>

      <v-row class="mb-4" align="center">
        <v-col cols="12" sm="4">
          <v-text-field
            v-model="searchQuery"
            prepend-inner-icon="mdi-magnify"
            label="現場名で検索"
            clearable
            hide-details
            density="compact"
          />
        </v-col>
        <v-col cols="12" sm="5">
          <v-btn-toggle v-model="statusFilter" mandatory color="primary" density="compact" divided>
            <v-btn value="all" size="small">すべて</v-btn>
            <v-btn value="normal" size="small">
              <v-icon icon="mdi-check-circle" size="16" class="mr-1" color="success" />
              正常
            </v-btn>
            <v-btn value="alert" size="small">
              <v-icon icon="mdi-alert-circle" size="16" class="mr-1" color="error" />
              欠測中
            </v-btn>
            <v-btn value="disabled" size="small">
              <v-icon icon="mdi-pause-circle" size="16" class="mr-1" color="grey" />
              無効
            </v-btn>
          </v-btn-toggle>
        </v-col>
        <v-col cols="12" sm="3" class="d-flex justify-end align-center ga-2">
          <v-btn-toggle v-model="ownerFilter" mandatory color="primary" density="compact" divided>
            <v-btn value="mine" size="small">自分</v-btn>
            <v-btn value="all" size="small">全体</v-btn>
          </v-btn-toggle>
          <v-btn
            :icon="autoRefresh ? 'mdi-sync' : 'mdi-sync-off'"
            :color="autoRefresh ? 'primary' : 'grey'"
            variant="text"
            size="small"
            @click="autoRefresh = !autoRefresh"
          >
            <v-icon :class="{ 'spin-icon': autoRefresh }" />
            <v-tooltip activator="parent" location="bottom">
              自動更新 (30秒) {{ autoRefresh ? 'ON' : 'OFF' }}
            </v-tooltip>
          </v-btn>
        </v-col>
      </v-row>

      <v-alert
        v-if="sitesStore.error"
        type="error"
        variant="tonal"
        class="mb-4"
      >
        <div class="d-flex align-center justify-space-between">
          <span>{{ sitesStore.error }}</span>
          <v-btn variant="text" color="error" size="small" @click="handleRetry">
            リトライ
          </v-btn>
        </div>
      </v-alert>

      <div v-if="!sitesStore.loading && filteredSites.length === 0 && sitesStore.sites.length === 0" class="text-center py-12">
        <v-icon icon="mdi-monitor-eye" size="80" color="grey-lighten-1" />
        <p class="text-h6 text-medium-emphasis mt-4">監視サイトが登録されていません</p>
        <p class="text-body-2 text-medium-emphasis mb-6">右下の + ボタンから最初のサイトを登録しましょう</p>
        <v-btn color="primary" prepend-icon="mdi-plus" @click="router.push('/sites/new')">
          サイトを登録する
        </v-btn>
      </div>

      <div v-else-if="!sitesStore.loading && filteredSites.length === 0" class="text-center py-12">
        <v-icon icon="mdi-magnify-close" size="64" color="grey-lighten-1" />
        <p class="text-h6 text-medium-emphasis mt-4">該当するサイトがありません</p>
        <p class="text-body-2 text-medium-emphasis">フィルター条件を変更してください</p>
      </div>

      <div v-else-if="sitesStore.loading && sitesStore.sites.length === 0">
        <v-row>
          <v-col v-for="i in 4" :key="i" cols="12" md="6">
            <v-skeleton-loader type="card" />
          </v-col>
        </v-row>
      </div>

      <v-row v-else>
        <v-col
          v-for="site in filteredSites"
          :key="site.site_id"
          cols="12"
          md="6"
        >
          <transition name="fade" appear>
            <SiteCard :site="site" @click="router.push(`/sites/${site.site_id}`)" />
          </transition>
        </v-col>
      </v-row>

      <v-btn
        icon="mdi-plus"
        color="primary"
        size="large"
        position="fixed"
        location="bottom end"
        class="ma-6 fab-btn"
        elevation="4"
        @click="router.push('/sites/new')"
      />
    </v-container>

    <v-snackbar v-model="snackbar" :timeout="3000" :color="snackbarColor">
      {{ snackbarText }}
    </v-snackbar>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useSitesStore } from '../stores/sites'
import { useAuthStore } from '../stores/auth'
import AppLayout from '../components/AppLayout.vue'
import SummaryCards from '../components/dashboard/SummaryCards.vue'
import SiteCard from '../components/dashboard/SiteCard.vue'

const router = useRouter()
const sitesStore = useSitesStore()
const authStore = useAuthStore()

const searchQuery = ref('')
const statusFilter = ref('all')
const ownerFilter = ref('mine')
const autoRefresh = ref(false)
const snackbar = ref(false)
const snackbarText = ref('')
const snackbarColor = ref('success')

let refreshTimer: ReturnType<typeof setInterval> | null = null

function startAutoRefresh() {
  stopAutoRefresh()
  refreshTimer = setInterval(async () => {
    await sitesStore.fetchSites()
  }, 30000)
}

function stopAutoRefresh() {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
}

watch(autoRefresh, (enabled) => {
  if (enabled) {
    startAutoRefresh()
    showMessage('自動更新を開始しました (30秒間隔)')
  } else {
    stopAutoRefresh()
  }
})

function showMessage(text: string, color: string = 'info') {
  snackbarText.value = text
  snackbarColor.value = color
  snackbar.value = true
}

async function handleRetry() {
  await sitesStore.fetchSites()
}

onMounted(async () => {
  await sitesStore.fetchSites()
})

onUnmounted(() => {
  stopAutoRefresh()
})

const filteredSites = computed(() => {
  let result = [...sitesStore.sites]

  if (ownerFilter.value === 'mine') {
    result = result.filter((s) => s.created_by === authStore.email)
  }

  if (statusFilter.value === 'normal') {
    result = result.filter((s) => s.enabled && s.last_check_status === 'updated')
  } else if (statusFilter.value === 'alert') {
    result = result.filter((s) => s.enabled && (s.last_check_status === 'not_updated' || s.last_check_status === 'error'))
  } else if (statusFilter.value === 'disabled') {
    result = result.filter((s) => !s.enabled)
  }

  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase()
    result = result.filter((s) => s.site_name.toLowerCase().includes(q))
  }

  return result.sort((a, b) => {
    const priority = (s: typeof a) => {
      if (!s.enabled) return 2
      if (s.last_check_status === 'not_updated' || s.last_check_status === 'error') return 0
      return 1
    }
    return priority(a) - priority(b)
  })
})
</script>

<style scoped>
.fab-btn {
  z-index: 100;
}
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
.spin-icon {
  animation: spin 2s linear infinite;
}
</style>
