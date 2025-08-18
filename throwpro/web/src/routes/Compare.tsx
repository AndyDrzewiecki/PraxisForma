import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { fetchFeatures } from '../api'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ReferenceArea } from 'recharts'
import { db, auth } from '../firebase'
import { collection, query, orderBy, limit as fbLimit, onSnapshot, where } from 'firebase/firestore'

type CurvePoint = { t_ms: number; [k: string]: number|null }

export function Compare() {
  const [sp, setSp] = useSearchParams()
  const a = sp.get('a') || ''
  const b = sp.get('b') || ''
  const metrics = (sp.get('metrics') || 'separation,ω_pelvis,ω_thorax,v_hand').split(',')
  const [dataA, setDataA] = useState<any|null>(null)
  const [dataB, setDataB] = useState<any|null>(null)
  const [error, setError] = useState<string>('')
  const [loading, setLoading] = useState<boolean>(false)
  const [showPelvis, setShowPelvis] = useState(true)
  const [showThorax, setShowThorax] = useState(true)
  const [showHand, setShowHand] = useState(true)
  const [suggestA, setSuggestA] = useState<string[]>([])
  const [suggestB, setSuggestB] = useState<string[]>([])

  useEffect(() => {
    async function go() {
      setError('')
      if (!a) { setDataA(null); setDataB(null); return }
      setLoading(true)
      try {
        const [fa, fb] = await Promise.all([
          fetchFeatures(a, metrics),
          b ? fetchFeatures(b, metrics) : Promise.resolve(null)
        ])
        setDataA(fa)
        setDataB(fb)
      } catch (e: any) {
        setError(e.message)
      } finally {
        setLoading(false)
      }
    }
    go()
  }, [a, b, sp.get('metrics')])

  useEffect(() => {
    // Load recent sessions for suggestions; widen to global if admin
    let unsub: any
    async function run() {
      const u = auth.currentUser
      if (!u) return
      let isAdmin = false
      try {
        const token = await u.getIdToken()
        const resp = await fetch(`${import.meta.env.VITE_API_BASE_URL}/admin/me`, { headers: { Authorization: `Bearer ${token}` } })
        if (resp.ok) { const b = await resp.json(); isAdmin = !!b.isAdmin }
      } catch {}
      const base = collection(db, 'throwSessions')
      const q = isAdmin ? query(base, orderBy('created_at', 'desc'), fbLimit(30)) : query(base, where('userId', '==', u.uid), orderBy('created_at', 'desc'), fbLimit(30))
      unsub = onSnapshot(q, (snap) => {
        const ids: string[] = []
        snap.forEach(d => ids.push(d.id))
        setSuggestA(ids)
        setSuggestB(ids)
        ;(window as any).throwproSessionIds = ids
      })
    }
    run()
    return () => unsub && unsub()
  }, [])

  const sepA = (dataA?.curves?.separation || []).map((p: any) => ({ t_ms: p.t_ms, sep: p.deg })) as CurvePoint[]
  const sepB = (dataB?.curves?.separation || []).map((p: any) => ({ t_ms: p.t_ms, sep: p.deg })) as CurvePoint[]
  const omegaPelvisA = (dataA?.curves?.['ω_pelvis']||[]).map((p:any)=>({ t_ms: p.t_ms, ω_pelvis: p.deg_s })) as CurvePoint[]
  const omegaThoraxA = (dataA?.curves?.['ω_thorax']||[]).map((p:any)=>({ t_ms: p.t_ms, ω_thorax: p.deg_s })) as CurvePoint[]
  const vHandA = (dataA?.curves?.v_hand||[]).map((p:any)=>({ t_ms: p.t_ms, v_hand: p.norm })) as CurvePoint[]

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold">Compare Sessions</h2>
      <Selector a={a} b={b} metrics={metrics} setSp={setSp} />
      {loading && <div className="text-sm text-gray-600">Loading…</div>}
      {error && <div className="text-sm text-red-600">{error}</div>}
      {!a && <div className="text-sm text-gray-600">Pick Session A to begin</div>}

      {!!a && (
        <div className="bg-white rounded shadow p-3">
          <div className="font-medium mb-2">Separation</div>
          <LineChart width={320} height={220} data={sepA}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="t_ms" tickFormatter={(v)=>String(v)} />
            <YAxis />
            <Tooltip />
            <Legend />
            {/* Envelope band shading if present */}
            {renderSeparationBand(dataA)}
            {/* Phase shading from phases */}
            {renderPhaseShading(dataA)}
            <Line type="monotone" dataKey="sep" data={sepA} stroke="#2e7d32" dot={false} name="A" />
            {sepB.length > 0 && <Line type="monotone" dataKey="sep" data={sepB} stroke="#1565c0" dot={false} name="B" />}
          </LineChart>
          {/* Badges */}
          <Badges data={dataA} />
        </div>
      )}

      {!!a && (
        <div className="bg-white rounded shadow p-3">
          <div className="flex items-center justify-between">
            <div className="font-medium mb-2">Angular velocities & hand</div>
            <div className="flex gap-3 text-xs">
              <label className="flex items-center gap-1"><input type="checkbox" checked={showPelvis} onChange={e=>setShowPelvis(e.target.checked)} /> ω_pelvis</label>
              <label className="flex items-center gap-1"><input type="checkbox" checked={showThorax} onChange={e=>setShowThorax(e.target.checked)} /> ω_thorax</label>
              <label className="flex items-center gap-1"><input type="checkbox" checked={showHand} onChange={e=>setShowHand(e.target.checked)} /> v_hand</label>
            </div>
          </div>
          <LineChart width={320} height={240} data={mergeSeries([omegaPelvisA, omegaThoraxA, vHandA])}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="t_ms" />
            <YAxis />
            <Tooltip />
            <Legend />
            {showPelvis && <Line type="monotone" dataKey="ω_pelvis" stroke="#ef6c00" dot={false} />}
            {showThorax && <Line type="monotone" dataKey="ω_thorax" stroke="#6a1b9a" dot={false} />}
            {showHand && <Line type="monotone" dataKey="v_hand" stroke="#0277bd" dot={false} />}
            {renderPeakMarkers(dataA)}
          </LineChart>
        </div>
      )}
    </div>
  )
}

function Selector({ a, b, metrics, setSp }: { a: string, b: string, metrics: string[], setSp: ReturnType<typeof useSearchParams>[1] }) {
  const [valA, setValA] = useState(a)
  const [valB, setValB] = useState(b)
  function apply() {
    const p = new URLSearchParams()
    if (valA) p.set('a', valA)
    if (valB) p.set('b', valB)
    if (metrics?.length) p.set('metrics', metrics.join(','))
    setSp(p)
  }
  return (
    <div className="flex gap-2 items-end">
      <div className="flex-1">
        <div className="text-xs text-gray-600">Session A</div>
        <input list="sessionAList" className="border rounded px-2 py-1 w-full" value={valA} onChange={e=>setValA(e.target.value)} placeholder="Session ID" />
        <datalist id="sessionAList">
          {(window as any).throwproSessionIds?.map?.((id:string)=> <option value={id} key={id} />)}
        </datalist>
      </div>
      <div className="flex-1">
        <div className="text-xs text-gray-600">Session B</div>
        <input list="sessionBList" className="border rounded px-2 py-1 w-full" value={valB} onChange={e=>setValB(e.target.value)} placeholder="Optional" />
        <datalist id="sessionBList">
          {(window as any).throwproSessionIds?.map?.((id:string)=> <option value={id} key={id} />)}
        </datalist>
      </div>
      <button className="px-3 py-1 border rounded" onClick={apply}>Load</button>
    </div>
  )
}

function mergeSeries(seriesList: CurvePoint[][]): CurvePoint[] {
  const map = new Map<number, any>()
  for (const series of seriesList) {
    for (const p of series) {
      const cur = map.get(p.t_ms) || { t_ms: p.t_ms }
      for (const [k, v] of Object.entries(p)) {
        if (k !== 't_ms') cur[k] = v as any
      }
      map.set(p.t_ms, cur)
    }
  }
  return Array.from(map.values()).sort((a,b)=>a.t_ms-b.t_ms)
}

function Badges({ data }: { data: any }) {
  const mf = data?.metrics_band_fit || {}
  const m = data?.metrics || {}
  const items: { key: string, label: string, value: number|undefined, fit: string }[] = [
    { key: 'Δhip_torso_ms', label: 'Δ hip→torso', value: m['Δhip_torso_ms'], fit: mf['Δhip_torso_ms'] },
    { key: 'Δtorso_hand_ms', label: 'Δ torso→hand', value: m['Δtorso_hand_ms'], fit: mf['Δtorso_hand_ms'] },
    { key: 'chain_order_score', label: 'Chain order', value: m['chain_order_score'], fit: mf['chain_order_score'] },
  ]
  function cls(fit?: string) {
    if (fit === 'inside') return 'bg-green-100 text-green-700'
    if (fit === 'near') return 'bg-amber-100 text-amber-700'
    return 'bg-red-100 text-red-700'
  }
  return (
    <div className="mt-2 flex gap-2 text-xs">
      {items.map(it => (
        <span key={it.key} className={`px-2 py-1 rounded ${cls(it.fit)}`}>{it.label}: {it.value ?? '-'}</span>
      ))}
    </div>
  )
}

function renderPhaseShading(data: any) {
  const phases = data?.phases || {}
  const all: any[] = []
  Object.entries(phases).forEach(([name, rng]: any) => {
    const [t0, t1] = rng || []
    if (typeof t0 === 'number' && typeof t1 === 'number' && t1 > t0) {
      all.push(<ReferenceArea key={`ph-${name}`} x1={t0} x2={t1} strokeOpacity={0.1} fill="#90caf9" ifOverflow="hidden" />)
    }
  })
  return all
}

function renderSeparationBand(data: any) {
  const env = data?.envelope || {}
  const band = env?.separation?.band || env?.separation_sequencing?.separation_deg || null
  if (!band || !Array.isArray(band) || band.length < 2) return null
  const [lo, hi] = band
  return <ReferenceArea y1={lo} y2={hi} fill="#c8e6c9" fillOpacity={0.4} ifOverflow="hidden" />
}

function renderPeakMarkers(data: any) {
  const series = data?.curves || {}
  const pel = series['ω_pelvis'] || []
  const thr = series['ω_thorax'] || []
  const hand = series['v_hand'] || []
  const peaks: number[] = []
  function peakT(xs: any[], key: string) {
    let best = -Infinity, t = undefined
    xs.forEach(p => {
      const v = (p[key] ?? 0) as number
      if (typeof v === 'number' && v > best) { best = v; t = p.t_ms }
    })
    return t
  }
  const tp = peakT(pel, 'deg_s'); if (tp) peaks.push(tp)
  const tt = peakT(thr, 'deg_s'); if (tt) peaks.push(tt)
  const th = peakT(hand, 'norm'); if (th) peaks.push(th)
  return peaks.map((t, i) => <ReferenceArea key={`pk-${i}`} x1={t} x2={t} stroke="#b71c1c" />)
}


