export interface SuspendConfig {
  enabled: boolean
  start: string
  end: string
  days: number[]
}

export interface Status {
  mode: string
  suspended: boolean
  last_update: string | null
  next_wake: string | null
  video?: string | null
  quote?: string | null
  suspend?: SuspendConfig
}
