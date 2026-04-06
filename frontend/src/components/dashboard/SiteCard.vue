<template>
  <v-card
    class="site-card"
    :style="{ borderLeft: `5px solid ${borderColor}` }"
    @click="$emit('click')"
    hover
  >
    <v-card-text class="pa-4">
      <div class="d-flex align-center justify-space-between mb-2">
        <div class="d-flex align-center">
          <v-chip
            :color="statusChipColor"
            :text="statusLabel"
            size="small"
            variant="flat"
            class="font-weight-medium mr-3"
          />
          <span class="text-h6 font-weight-bold">{{ site.site_name }}</span>
        </div>
        <v-chip
          :prepend-icon="monitorIcon"
          :text="monitorLabel"
          size="small"
          variant="tonal"
          color="primary"
        />
      </div>

      <v-divider class="my-3" />

      <div class="d-flex flex-wrap ga-4 text-body-2 text-medium-emphasis">
        <div class="d-flex align-center">
          <v-icon icon="mdi-clock-outline" size="16" class="mr-1" />
          最終チェック: {{ formattedLastChecked }}
        </div>
        <div v-if="site.consecutive_miss_count > 0" class="d-flex align-center">
          <v-icon icon="mdi-alert-outline" size="16" class="mr-1" color="error" />
          <span class="text-error font-weight-medium">
            連続欠測: {{ site.consecutive_miss_count }}回
          </span>
        </div>
        <div class="d-flex align-center">
          <v-icon icon="mdi-timer-outline" size="16" class="mr-1" />
          {{ site.schedule_interval_minutes }}分間隔
        </div>
      </div>

      <div class="d-flex align-center justify-space-between mt-3">
        <div class="d-flex align-center text-caption text-disabled">
          <v-icon icon="mdi-account-outline" size="14" class="mr-1" />
          {{ site.created_by }}
        </div>
        <div class="d-flex ga-1">
          <v-btn
            icon="mdi-history"
            variant="text"
            size="x-small"
            color="primary"
            :to="`/sites/${site.site_id}/history`"
            @click.stop
          />
          <v-btn
            icon="mdi-bell-outline"
            variant="text"
            size="x-small"
            color="primary"
            :to="`/sites/${site.site_id}/notifications`"
            @click.stop
          />
        </div>
      </div>
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Site } from '../../data/mock-data'

const props = defineProps<{
  site: Site
}>()

defineEmits<{
  click: []
}>()

const borderColor = computed(() => {
  if (!props.site.enabled) return '#9CA3AF'
  if (props.site.last_check_status === 'updated') return '#16A34A'
  return '#DC2626'
})

const statusChipColor = computed(() => {
  if (!props.site.enabled) return 'grey'
  if (props.site.last_check_status === 'updated') return 'success'
  if (props.site.last_check_status === 'error') return 'error'
  return 'error'
})

const statusLabel = computed(() => {
  if (!props.site.enabled) return '無効'
  if (props.site.last_check_status === 'updated') return '正常'
  if (props.site.last_check_status === 'error') return 'エラー'
  return '欠測中'
})

const monitorIcon = computed(() =>
  props.site.monitor_type === 'url_check' ? 'mdi-web' : 'mdi-cloud-outline',
)

const monitorLabel = computed(() =>
  props.site.monitor_type === 'url_check' ? 'URL監視' : 'CWログ監視',
)

const formattedLastChecked = computed(() => {
  const date = new Date(props.site.last_checked_at)
  return date.toLocaleString('ja-JP', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
})
</script>

<style scoped>
.site-card {
  transition: transform 0.2s ease, box-shadow 0.2s ease;
  border: 1px solid #E2E8F0;
  cursor: pointer;
}
.site-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
}
</style>
