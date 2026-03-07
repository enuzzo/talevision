export interface SuspendConfig {
  enabled: boolean
  start: string
  end: string
  days: number[]
}

export interface ModeInterval {
  effective: number
  default: number
  overridden: boolean
}

export interface Status {
  mode: string
  suspended: boolean
  last_update: string | null
  next_wake: string | null
  video?: string | null
  quote?: string | null
  suspend?: SuspendConfig
  intervals?: Record<string, ModeInterval>
  playlist?: string[]
  playlist_index?: number
  rotation_interval?: number
}
