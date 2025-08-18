import { useEffect, useMemo, useState } from 'react'
import { auth } from '../firebase'

type Key = 'event'|'ageBand'|'sex'|'handedness'

const defaultKey = { event: 'discus', ageBand: 'Open', sex: 'M', handedness: 'right' }

export function AdminCalibration() {
  const [key, setKey] = useState(defaultKey)
  const [items, setItems] = useState<any[]>([])
  const [form, setForm] = useState<any>({ components: {}, timing_windows: {}, notes: '' })
  const [selectedId, setSelectedId] = useState<string>('')
  const [message, setMessage] = useState<string>('')
  const [sourceV2, setSourceV2] = useState<boolean>(false)
  const [v2Bands, setV2Bands] = useState<any|null>(null)

  async function fetchList() {
    const token = await auth.currentUser?.getIdToken()
    const qs = new URLSearchParams(key as any).toString()
    const resp = await fetch(`${import.meta.env.VITE_API_BASE_URL}/admin/envelopes/list?${qs}`, { headers: { Authorization: `Bearer ${token}` } })
    if (resp.ok) { const body = await resp.json(); setItems(body.items || []) }
  }

  useEffect(() => { fetchList() }, [key.event, key.ageBand, key.sex, key.handedness])
  useEffect(() => { if (sourceV2) fetchV2() }, [sourceV2, key.event, key.ageBand, key.sex, key.handedness])

  async function saveDraft() {
    setMessage('')
    const token = await auth.currentUser?.getIdToken()
    const payload = { ...key, components: form.components || {}, timing_windows: form.timing_windows || {}, notes: form.notes || '' }
    const resp = await fetch(`${import.meta.env.VITE_API_BASE_URL}/admin/envelopes`, { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` }, body: JSON.stringify(payload) })
    if (resp.ok) { setMessage('Draft saved'); fetchList() } else { setMessage('Save failed') }
  }

  async function activate(version: number) {
    setMessage('')
    const token = await auth.currentUser?.getIdToken()
    const resp = await fetch(`${import.meta.env.VITE_API_BASE_URL}/admin/envelopes/activate`, { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` }, body: JSON.stringify({ ...key, version }) })
    setMessage(resp.ok ? 'Activated' : 'Activate failed')
  }

  async function fetchV2() {
    setMessage('')
    const token = await auth.currentUser?.getIdToken()
    const resp = await fetch(`${import.meta.env.VITE_API_BASE_URL}/admin/envelopes2?level=${key.ageBand}&sex=${key.sex}&hand=${key.handedness === 'right' ? 'R':'L'}`, { headers: { Authorization: `Bearer ${token}` } })
    if (resp.ok) { const body = await resp.json(); setV2Bands(body) }
  }
  async function saveV2(bands: any) {
    const token = await auth.currentUser?.getIdToken()
    const payload = { level: key.ageBand, sex: key.sex, hand: key.handedness === 'right' ? 'R':'L', bands }
    const resp = await fetch(`${import.meta.env.VITE_API_BASE_URL}/admin/envelopes2`, { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` }, body: JSON.stringify(payload) })
    setMessage(resp.ok ? 'Saved v2' : 'Save failed')
    if (resp.ok) fetchV2()
  }

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold">Admin Calibration Console</h2>
      {message && <div className="text-sm text-gray-700">{message}</div>}
      <div className="grid grid-cols-2 gap-3">
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={sourceV2} onChange={e=>setSourceV2(e.target.checked)} /> Use JSON/GCS envelopes (v2)</label>
        <select value={key.event} onChange={e=>setKey(prev=>({...prev, event:e.target.value}))}>
          {['discus','shot_put_rotational','shot_put_glide'].map(v=> <option key={v} value={v}>{v}</option>)}
        </select>
        <select value={key.ageBand} onChange={e=>setKey(prev=>({...prev, ageBand:e.target.value}))}>
          {['U14','U16','U18','U20','Open'].map(v=> <option key={v} value={v}>{v}</option>)}
        </select>
        <select value={key.sex} onChange={e=>setKey(prev=>({...prev, sex:e.target.value}))}>
          {['M','F'].map(v=> <option key={v} value={v}>{v}</option>)}
        </select>
        <select value={key.handedness} onChange={e=>setKey(prev=>({...prev, handedness:e.target.value}))}>
          {['left','right'].map(v=> <option key={v} value={v}>{v}</option>)}
        </select>
      </div>

      <div className="bg-white rounded shadow p-3">
        {!sourceV2 && (
          <>
            <div className="font-medium mb-2">Components JSON (legacy Firestore)</div>
            <textarea className="w-full h-40 border rounded p-2 font-mono text-xs" value={JSON.stringify(form.components || {}, null, 2)} onChange={e=> setForm((f:any)=> ({...f, components: safeParse(e.target.value)}))} />
            <div className="font-medium mt-3 mb-2">Timing Windows JSON</div>
            <textarea className="w-full h-40 border rounded p-2 font-mono text-xs" value={JSON.stringify(form.timing_windows || {}, null, 2)} onChange={e=> setForm((f:any)=> ({...f, timing_windows: safeParse(e.target.value)}))} />
            <input className="w-full border rounded px-2 py-1 mt-2" placeholder="Notes" value={form.notes || ''} onChange={e=> setForm((f:any)=> ({...f, notes: e.target.value}))} />
            <div className="mt-3 flex gap-2">
              <button className="px-4 py-2 bg-blue-600 text-white rounded" onClick={saveDraft}>Save Draft</button>
            </div>
          </>
        )}
        {sourceV2 && (
          <>
            <div className="font-medium mb-2">Envelopes v2 (JSON/GCS)</div>
            <div className="text-xs text-gray-600 mb-2">Source: {v2Bands?.source ?? '-'}</div>
            <textarea className="w-full h-64 border rounded p-2 font-mono text-xs" value={JSON.stringify(v2Bands?.bands || {}, null, 2)} onChange={e=> setV2Bands((prev:any)=> ({...(prev||{}), bands: safeParse(e.target.value)}))} />
            <div className="mt-3 flex gap-2">
              <button className="px-4 py-2 bg-blue-600 text-white rounded" onClick={()=> saveV2(v2Bands?.bands || {})}>Save v2</button>
              <button className="px-4 py-2 border rounded" onClick={fetchV2}>Refresh</button>
              <SeedButtons onSeed={saveV2} />
            </div>
          </>
        )}
      </div>

      <div className="bg-white rounded shadow p-3">
        <div className="font-medium mb-2">Versions</div>
        <div className="space-y-2">
          {items.map((it:any)=> (
            <div key={it.id} className="flex items-center justify-between border rounded p-2">
              <div>
                <div className="text-sm">v{it.version} {it.is_active ? '(active)' : ''}</div>
                <div className="text-xs text-gray-600">{it.notes}</div>
              </div>
              <div className="flex gap-2">
                <button className="text-sm text-blue-600" onClick={()=> activate(it.version)}>Activate</button>
              </div>
            </div>
          ))}
        </div>
      </div>

      <CompareBlock />
    </div>
  )
}

function safeParse(text: string) {
  try { return JSON.parse(text) } catch { return {} }
}

function SeedButtons({ onSeed }: { onSeed: (bands: any) => void }) {
  const [busy, setBusy] = useState(false)
  async function seed(which: 'discus'|'shot') {
    setBusy(true)
    try {
      const { discusOpenMRight, shotRotOpenMRight } = await import('../data/envelopeSeeds')
      onSeed(which === 'discus' ? discusOpenMRight : shotRotOpenMRight)
    } finally { setBusy(false) }
  }
  return (
    <div className="flex gap-2">
      <button disabled={busy} className="px-3 py-1 border rounded" onClick={()=>seed('discus')}>Seed discus</button>
      <button disabled={busy} className="px-3 py-1 border rounded" onClick={()=>seed('shot')}>Seed shot</button>
    </div>
  )
}

function CompareBlock() {
  const [sessionId, setSessionId] = useState('')
  const [data, setData] = useState<any>(null)
  async function load() {
    const token = await auth.currentUser?.getIdToken()
    const resp = await fetch(`${import.meta.env.VITE_API_BASE_URL}/sessions/${sessionId}/features?curves=separation,ω_pelvis,ω_thorax,v_hand`, {
      headers: { Authorization: `Bearer ${token}` }
    })
    if (resp.ok) setData(await resp.json())
  }
  return (
    <div className="bg-white rounded shadow p-3">
      <div className="font-medium mb-2">Compare Session</div>
      <div className="flex gap-2 mb-2">
        <input className="border rounded px-2 py-1 flex-1" placeholder="Session ID" value={sessionId} onChange={e=>setSessionId(e.target.value)} />
        <button className="px-3 py-1 border rounded" onClick={load}>Load</button>
      </div>
      {data && (
        <div className="text-sm text-gray-700">Envelope version used: {data.envelope_version ?? '-'}</div>
      )}
      {data && (
        <div className="text-xs text-gray-600">
          Points: separation={data.curves?.separation?.length ?? 0}, ω_pelvis={data.curves?.['ω_pelvis']?.length ?? 0}, ω_thorax={data.curves?.['ω_thorax']?.length ?? 0}, v_hand={data.curves?.v_hand?.length ?? 0}
        </div>
      )}
    </div>
  )
}


