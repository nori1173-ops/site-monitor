import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../services/api'
import type { Site, CheckResult, StatusChange, Notification } from '../data/mock-data'

export const useSitesStore = defineStore('sites', () => {
  const sites = ref<Site[]>([])
  const checkResults = ref<CheckResult[]>([])
  const statusChanges = ref<StatusChange[]>([])
  const notifications = ref<Notification[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

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

  async function fetchSites(filter?: string): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const params = filter ? { filter } : {}
      const response = await api.get('/sites', { params })
      sites.value = response.data.data ?? []
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : 'サイト一覧の取得に失敗しました'
    } finally {
      loading.value = false
    }
  }

  async function fetchSiteById(siteId: string): Promise<Site | null> {
    try {
      const response = await api.get(`/sites/${siteId}`)
      return response.data.data ?? null
    } catch {
      return null
    }
  }

  async function createSite(siteData: Partial<Site>): Promise<Site | null> {
    loading.value = true
    error.value = null
    try {
      const response = await api.post('/sites', siteData)
      const newSite = response.data.data
      if (newSite) {
        sites.value = [...sites.value, newSite]
      }
      return newSite
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : 'サイトの作成に失敗しました'
      return null
    } finally {
      loading.value = false
    }
  }

  async function updateSite(siteId: string, updates: Partial<Site>): Promise<Site | null> {
    loading.value = true
    error.value = null
    try {
      const response = await api.put(`/sites/${siteId}`, updates)
      const updatedSite = response.data.data
      if (updatedSite) {
        sites.value = sites.value.map((s) =>
          s.site_id === siteId ? updatedSite : s,
        )
      }
      return updatedSite
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : 'サイトの更新に失敗しました'
      return null
    } finally {
      loading.value = false
    }
  }

  async function deleteSite(siteId: string): Promise<boolean> {
    loading.value = true
    error.value = null
    try {
      await api.delete(`/sites/${siteId}`)
      sites.value = sites.value.filter((s) => s.site_id !== siteId)
      return true
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : 'サイトの削除に失敗しました'
      return false
    } finally {
      loading.value = false
    }
  }

  async function fetchCheckResults(siteId: string): Promise<void> {
    try {
      const response = await api.get(`/sites/${siteId}/results`)
      const results = response.data.data ?? []
      checkResults.value = [
        ...checkResults.value.filter((r) => r.site_id !== siteId),
        ...results,
      ]
    } catch {
      // silent fail
    }
  }

  async function fetchStatusChanges(siteId: string): Promise<void> {
    try {
      const response = await api.get(`/sites/${siteId}/status-changes`)
      const changes = response.data.data ?? []
      statusChanges.value = [
        ...statusChanges.value.filter((c) => c.site_id !== siteId),
        ...changes,
      ]
    } catch {
      // silent fail
    }
  }

  async function fetchNotifications(siteId: string): Promise<void> {
    try {
      const response = await api.get(`/sites/${siteId}/notifications`)
      const notifs = response.data.data ?? []
      notifications.value = [
        ...notifications.value.filter((n) => n.site_id !== siteId),
        ...notifs,
      ]
    } catch {
      // silent fail
    }
  }

  async function createNotification(siteId: string, data: Partial<Notification>): Promise<Notification | null> {
    try {
      const response = await api.post(`/sites/${siteId}/notifications`, data)
      const notif = response.data.data
      if (notif) {
        notifications.value = [...notifications.value, notif]
      }
      return notif
    } catch {
      return null
    }
  }

  async function updateNotification(siteId: string, notificationId: string, data: Partial<Notification>): Promise<Notification | null> {
    try {
      const response = await api.put(`/sites/${siteId}/notifications/${notificationId}`, data)
      const updated = response.data.data
      if (updated) {
        notifications.value = notifications.value.map((n) =>
          n.notification_id === notificationId ? updated : n,
        )
      }
      return updated
    } catch {
      return null
    }
  }

  async function deleteNotification(siteId: string, notificationId: string): Promise<boolean> {
    try {
      await api.delete(`/sites/${siteId}/notifications/${notificationId}`)
      notifications.value = notifications.value.filter((n) => n.notification_id !== notificationId)
      return true
    } catch {
      return false
    }
  }

  async function testCheck(siteId: string): Promise<unknown> {
    const response = await api.post(`/sites/${siteId}/test-check`)
    return response.data.data
  }

  async function testNotify(siteId: string): Promise<unknown> {
    const response = await api.post(`/sites/${siteId}/test-notify`)
    return response.data.data
  }

  async function fetchLogGroups(): Promise<{ logGroupName: string }[]> {
    try {
      const response = await api.get('/cloudwatch/log-groups')
      return response.data.data ?? []
    } catch {
      return []
    }
  }

  return {
    sites,
    checkResults,
    statusChanges,
    notifications,
    loading,
    error,
    enabledSites,
    normalCount,
    alertCount,
    disabledCount,
    getSiteById,
    getCheckResultsBySiteId,
    getStatusChangesBySiteId,
    getNotificationsBySiteId,
    fetchSites,
    fetchSiteById,
    createSite,
    updateSite,
    deleteSite,
    fetchCheckResults,
    fetchStatusChanges,
    fetchNotifications,
    createNotification,
    updateNotification,
    deleteNotification,
    testCheck,
    testNotify,
    fetchLogGroups,
  }
})
