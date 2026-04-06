<template>
  <AppLayout>
    <v-container class="py-6" fluid style="max-width: 1200px">
      <SummaryCards class="mb-6" />

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
        <v-col cols="12" sm="3" class="d-flex justify-end">
          <v-btn-toggle v-model="ownerFilter" mandatory color="primary" density="compact" divided>
            <v-btn value="mine" size="small">自分</v-btn>
            <v-btn value="all" size="small">全体</v-btn>
          </v-btn-toggle>
        </v-col>
      </v-row>

      <div v-if="filteredSites.length === 0" class="text-center py-12">
        <v-icon icon="mdi-magnify-close" size="64" color="grey-lighten-1" />
        <p class="text-h6 text-medium-emphasis mt-4">該当するサイトがありません</p>
      </div>

      <v-row v-else>
        <v-col v-for="site in filteredSites" :key="site.site_id" cols="12" md="6">
          <SiteCard :site="site" @click="router.push(`/sites/${site.site_id}`)" />
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
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
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

onMounted(async () => {
  await sitesStore.fetchSites()
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
</style>
