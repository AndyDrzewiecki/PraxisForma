export type Phases = Record<string, [number, number]>

export type FeatureCurves = {
  curves: {
    separation?: { t_ms: number; deg: number|null }[]
    ['ω_pelvis']?: { t_ms: number; deg_s: number|null }[]
    ['ω_thorax']?: { t_ms: number; deg_s: number|null }[]
    v_hand?: { t_ms: number; norm: number|null }[]
  }
  phases: Phases
  envelope?: any
  metrics?: Record<string, number>
  envelope_version?: string|number
}

export async function fetchFeatures(sessionId: string, metrics: string[]): Promise<FeatureCurves> {
  const token = await (await import('./firebase')).auth.currentUser?.getIdToken()
  const qs = new URLSearchParams({ v: '2', curves: metrics.join(',') }).toString()
  const resp = await fetch(`${import.meta.env.VITE_API_BASE_URL}/sessions/${sessionId}/features?${qs}`, {
    headers: { Authorization: `Bearer ${token}` }
  })
  if (!resp.ok) throw new Error(`Failed to load features: ${resp.status}`)
  return await resp.json()
}

export type ProgressItem = {
  id: string
  created_at?: string|null
  total?: number|null
  release_angle_deg?: number|null
  chain_order_score?: number|null
  v_hand_peak_norm?: number|null
}

export async function fetchProgress(athleteId: string, opts: { metrics?: string[], limit?: number, cursor?: string } = {}) {
  const token = await (await import('./firebase')).auth.currentUser?.getIdToken()
  const params: any = {}
  if (opts.metrics?.length) params.metrics = opts.metrics.join(',')
  if (opts.limit) params.limit = String(opts.limit)
  if (opts.cursor) params.cursor = opts.cursor
  const qs = new URLSearchParams(params).toString()
  const resp = await fetch(`${import.meta.env.VITE_API_BASE_URL}/athletes/${athleteId}/progress?${qs}`, { headers: { Authorization: `Bearer ${token}` } })
  if (!resp.ok) throw new Error(`Failed to load progress: ${resp.status}`)
  return await resp.json() as { items: ProgressItem[], next_cursor?: string }
}


