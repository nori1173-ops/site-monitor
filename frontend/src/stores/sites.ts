import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { mockSites, mockCheckResults, mockStatusChanges, mockNotifications } from '../data/mock-data'
import type { Site, CheckResult, StatusChange, Notification } from '../data/mock-data'

export const useSitesStore = defineStore('sites', () => {
  const sites = ref<Site[]>(mockSites)
  const checkResults = ref<CheckResult[]>(mockCheckResults)
  const statusChanges = ref<StatusChange[]>(mockStatusChanges)
  const notifications = ref<Notification[]>(mockNotifications)

  const enabledSites = computed(() => sites.value.filter((s) => s.enabled))
  const normalCount = computed(() => enabledSites.value.filter((s) => s.last_check_status === 'updated').length)
  const alertCount = computed(() => enabledSites.value.filter((s) => s.last_check_status === 'not_updated' || s.last_check_status === 'error').length)
  const disabledCount = computed(() => sites.value.filter((s) => !s.enabled).length)

  function getSiteById(id: string): Site | undefined {
    return sites.value.find((s) => s.site_id === id)
  }

  function getCheckResultsBySiteId(siteId: string): CheckResult[] {
    return checkResults.value.filter((r) => r.site_id === siteId)
  }

  function getStatusChangesBySiteId(siteId: string): StatusChange[] {
    return statusChanges.value.filter((c) => c.site_id === siteId)
  }

  function getNotificationsBySiteId(siteId: string): Notification[] {
    return notifications.value.filter((n) => n.site_id === siteId)
  }

  function addSite(site: Site): void {
    sites.value = [...sites.value, site]
  }

  function updateSite(siteId: string, updates: Partial<Site>): void {
    sites.value = sites.value.map((s) =>
      s.site_id === siteId ? { ...s, ...updates } : s,
    )
  }

  function deleteSite(siteId: string): void {
    sites.value = sites.value.filter((s) => s.site_id !== siteId)
  }

  return {
    sites,
    checkResults,
    statusChanges,
    notifications,
    enabledSites,
    normalCount,
    alertCount,
    disabledCount,
    getSiteById,
    getCheckResultsBySiteId,
    getStatusChangesBySiteId,
    getNotificationsBySiteId,
    addSite,
    updateSite,
    deleteSite,
  }
})
