export interface UrlTarget {
  url: string
}

export interface CloudWatchLogTarget {
  log_group: string
  message_filter: string
  json_search_word: string
  search_period_minutes: number
}

export type MonitorTarget = UrlTarget | CloudWatchLogTarget

export interface Site {
  site_id: string
  site_name: string
  monitor_type: 'url_check' | 'cloudwatch_log'
  targets: MonitorTarget[]
  schedule_start: string
  schedule_interval_minutes: number
  consecutive_threshold: number
  enabled: boolean
  last_check_status: 'updated' | 'not_updated' | 'error'
  last_checked_at: string
  consecutive_miss_count: number
  created_by: string
  updated_by: string
  created_at: string
  updated_at: string
}

export interface CheckResult {
  site_id: string
  checked_at: string
  target_url: string
  status: 'updated' | 'not_updated' | 'error'
  consecutive_miss_count: number
}

export interface StatusChange {
  site_id: string
  changed_at: string
  previous_status: string
  new_status: string
  trigger_url: string
}

export interface Notification {
  site_id: string
  notification_id: string
  type: 'email' | 'slack'
  destination: string
  mention: string
  message_template: string
  enabled: boolean
}

export const mockSites: Site[] = [
  {
    site_id: 'site-001',
    site_name: '○○ダム',
    monitor_type: 'url_check',
    targets: [
      { url: 'https://example.com/dam/latest.png' },
      { url: 'https://example.com/dam/graph.html' },
    ],
    schedule_start: '00:20',
    schedule_interval_minutes: 60,
    consecutive_threshold: 3,
    enabled: true,
    last_check_status: 'updated',
    last_checked_at: '2026-04-06T09:20:00+09:00',
    consecutive_miss_count: 0,
    created_by: 'miyaji@osasi.co.jp',
    updated_by: 'miyaji@osasi.co.jp',
    created_at: '2026-03-15T10:00:00+09:00',
    updated_at: '2026-04-01T14:30:00+09:00',
  },
  {
    site_id: 'site-002',
    site_name: '△△橋梁',
    monitor_type: 'url_check',
    targets: [
      { url: 'https://example.com/bridge/data.html' },
    ],
    schedule_start: '00:05',
    schedule_interval_minutes: 10,
    consecutive_threshold: 5,
    enabled: true,
    last_check_status: 'not_updated',
    last_checked_at: '2026-04-06T10:05:00+09:00',
    consecutive_miss_count: 4,
    created_by: 'tanaka@osasi.co.jp',
    updated_by: 'tanaka@osasi.co.jp',
    created_at: '2026-03-20T11:00:00+09:00',
    updated_at: '2026-03-20T11:00:00+09:00',
  },
  {
    site_id: 'site-003',
    site_name: '□□発電所',
    monitor_type: 'cloudwatch_log',
    targets: [
      {
        log_group: 'DataTransferSystem2-OsBoard-Function1',
        message_filter: 'リクエストを送信します。',
        json_search_word: '"account": "10206721","note": "LONG"',
        search_period_minutes: 60,
      },
    ],
    schedule_start: '00:50',
    schedule_interval_minutes: 60,
    consecutive_threshold: 3,
    enabled: true,
    last_check_status: 'error',
    last_checked_at: '2026-04-06T09:50:00+09:00',
    consecutive_miss_count: 2,
    created_by: 'miyaji@osasi.co.jp',
    updated_by: 'suzuki@osasi.co.jp',
    created_at: '2026-03-25T09:00:00+09:00',
    updated_at: '2026-04-05T16:00:00+09:00',
  },
  {
    site_id: 'site-004',
    site_name: '◇◇観測所',
    monitor_type: 'url_check',
    targets: [
      { url: 'https://example.com/observatory/status.png' },
    ],
    schedule_start: '00:00',
    schedule_interval_minutes: 360,
    consecutive_threshold: 2,
    enabled: false,
    last_check_status: 'updated',
    last_checked_at: '2026-04-05T18:00:00+09:00',
    consecutive_miss_count: 0,
    created_by: 'suzuki@osasi.co.jp',
    updated_by: 'suzuki@osasi.co.jp',
    created_at: '2026-04-01T08:00:00+09:00',
    updated_at: '2026-04-01T08:00:00+09:00',
  },
  {
    site_id: 'site-005',
    site_name: '▽▽水位計',
    monitor_type: 'cloudwatch_log',
    targets: [
      {
        log_group: 'NetMAIL-Backend-Subscriber',
        message_filter: 'メールを配信します。',
        json_search_word: '10206721@ml.osasi-cloud.com',
        search_period_minutes: 60,
      },
    ],
    schedule_start: '00:30',
    schedule_interval_minutes: 60,
    consecutive_threshold: 3,
    enabled: true,
    last_check_status: 'not_updated',
    last_checked_at: '2026-04-06T10:30:00+09:00',
    consecutive_miss_count: 7,
    created_by: 'tanaka@osasi.co.jp',
    updated_by: 'miyaji@osasi.co.jp',
    created_at: '2026-03-18T13:00:00+09:00',
    updated_at: '2026-04-04T10:00:00+09:00',
  },
]

export const mockCheckResults: CheckResult[] = [
  { site_id: 'site-001', checked_at: '2026-04-06T09:20:00+09:00', target_url: 'https://example.com/dam/latest.png', status: 'updated', consecutive_miss_count: 0 },
  { site_id: 'site-001', checked_at: '2026-04-06T08:20:00+09:00', target_url: 'https://example.com/dam/latest.png', status: 'updated', consecutive_miss_count: 0 },
  { site_id: 'site-001', checked_at: '2026-04-06T07:20:00+09:00', target_url: 'https://example.com/dam/latest.png', status: 'not_updated', consecutive_miss_count: 1 },
  { site_id: 'site-002', checked_at: '2026-04-06T10:05:00+09:00', target_url: 'https://example.com/bridge/data.html', status: 'not_updated', consecutive_miss_count: 4 },
  { site_id: 'site-002', checked_at: '2026-04-06T09:55:00+09:00', target_url: 'https://example.com/bridge/data.html', status: 'not_updated', consecutive_miss_count: 3 },
  { site_id: 'site-002', checked_at: '2026-04-06T09:45:00+09:00', target_url: 'https://example.com/bridge/data.html', status: 'not_updated', consecutive_miss_count: 2 },
]

export const mockStatusChanges: StatusChange[] = [
  { site_id: 'site-002', changed_at: '2026-04-06T09:15:00+09:00', previous_status: 'updated', new_status: 'not_updated', trigger_url: 'https://example.com/bridge/data.html' },
  { site_id: 'site-003', changed_at: '2026-04-06T08:50:00+09:00', previous_status: 'updated', new_status: 'error', trigger_url: 'DataTransferSystem2-OsBoard-Function1' },
  { site_id: 'site-001', changed_at: '2026-04-05T15:20:00+09:00', previous_status: 'not_updated', new_status: 'updated', trigger_url: 'https://example.com/dam/latest.png' },
  { site_id: 'site-005', changed_at: '2026-04-06T07:30:00+09:00', previous_status: 'updated', new_status: 'not_updated', trigger_url: 'NetMAIL-Backend-Subscriber' },
]

export const mockNotifications: Notification[] = [
  { site_id: 'site-001', notification_id: 'notif-001', type: 'email', destination: 'miyaji@osasi.co.jp', mention: '', message_template: '', enabled: true },
  { site_id: 'site-001', notification_id: 'notif-002', type: 'slack', destination: '/web-alive/slack-webhook-url', mention: '@channel', message_template: '', enabled: true },
  { site_id: 'site-002', notification_id: 'notif-003', type: 'email', destination: 'tanaka@osasi.co.jp', mention: '', message_template: '', enabled: true },
]
