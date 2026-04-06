<template>
  <v-row>
    <v-col v-for="card in cards" :key="card.title" cols="6" md="3">
      <v-card
        :style="{ borderTop: `4px solid ${card.color}` }"
        class="pa-4 summary-card"
      >
        <div class="d-flex align-center justify-space-between">
          <div>
            <div class="text-caption text-medium-emphasis font-weight-medium text-uppercase tracking-wide">
              {{ card.title }}
            </div>
            <div class="text-h4 font-weight-bold mt-1" :style="{ color: card.color }">
              {{ card.value }}
            </div>
          </div>
          <v-avatar :color="card.bgColor" size="48">
            <v-icon :icon="card.icon" :color="card.color" size="24" />
          </v-avatar>
        </div>
      </v-card>
    </v-col>
  </v-row>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useSitesStore } from '../../stores/sites'

const store = useSitesStore()

const cards = computed(() => [
  {
    title: '監視中',
    value: store.enabledSites.length,
    icon: 'mdi-monitor-eye',
    color: '#1E40AF',
    bgColor: '#DBEAFE',
  },
  {
    title: '正常',
    value: store.normalCount,
    icon: 'mdi-check-circle-outline',
    color: '#16A34A',
    bgColor: '#DCFCE7',
  },
  {
    title: '欠測中',
    value: store.alertCount,
    icon: 'mdi-alert-circle-outline',
    color: '#DC2626',
    bgColor: '#FEE2E2',
  },
  {
    title: '無効',
    value: store.disabledCount,
    icon: 'mdi-pause-circle-outline',
    color: '#9CA3AF',
    bgColor: '#F3F4F6',
  },
])
</script>

<style scoped>
.summary-card {
  transition: transform 0.2s ease, box-shadow 0.2s ease;
  border: 1px solid #E2E8F0;
}
.summary-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}
.tracking-wide {
  letter-spacing: 0.05em;
}
</style>
