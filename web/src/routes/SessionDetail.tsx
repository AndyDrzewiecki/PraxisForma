import { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { auth, db } from '../firebase'
import { doc, onSnapshot } from 'firebase/firestore'
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer } from 'recharts'

export function SessionDetail() {
  const { sessionId } = useParams()
  const [data, setData] = useState<any>(null)
  const [videoUrl, setVideoUrl] = useState<string>('')
  const [overlayUrl, setOverlayUrl] = useState<string>('')
  const [overlayBusy, setOverlayBusy] = useState<boolean>(false)
  const [status, setStatus] = useState<string>('')

  useEffect(() => {
    if (!sessionId) return
    const unsub = onSnapshot(doc(db, 'throwSessions', sessionId), (docSnap) => {
      const d = docSnap.data() as any
      setData(d)
      const st = d?.status?.state || ''
      setStatus(st)
      const ov = d?.assets?.overlay_uri
      if (ov) fetchOverlayUrl(ov)
    })
    return () => unsub()
  }, [sessionId])

  const chartData = useMemo(() => {
    if (!data?.pqs?.components) return []
    const c = data.pqs.components
    return [
      { k: 'Shoulders', v: c.shoulder_alignment },
      { k: 'Hips', v: c.hip_rotation },
      { k: 'Release', v: c.release_angle },
      { k: 'Power', v: c.power_transfer },
      { k: 'Footwork', v: c.footwork_timing },
    ]
  }, [data])

  const chartV2 = useMemo(() => {
    const c = data?.pqs_v2?.components
    if (!c) return []
    return [
      { k: 'Platform', v: c.lower_body_platform },
      { k: 'Separation', v: c.separation_sequencing },
      { k: 'Kinetics', v: c.arm_implement_kinetics },
      { k: 'Release', v: c.release_quality },
      { k: 'Smooth', v: c.smoothness_control },
    ]
  }, [data])

  async function playBlurred() {
    const token = await auth.currentUser?.getIdToken()
    const resp = await fetch(`${import.meta.env.VITE_API_BASE_URL}/signed-url`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      body: JSON.stringify({ gs_uri: data.blurred_uri })
    })
    if (resp.ok) {
      const body = await resp.json()
      setVideoUrl(body.url)
    }
  }

  async function generateOverlay() {
    if (!sessionId) return
    setOverlayBusy(true)
    try {
      const token = await auth.currentUser?.getIdToken()
      const resp = await fetch(`${import.meta.env.VITE_API_BASE_URL}/sessions/${sessionId}/overlay`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
      })
      if (resp.ok) {
        // Poll Firestore until assets.overlay_uri exists
        let tries = 0
        const unsub = onSnapshot(doc(db, 'throwSessions', sessionId), (snap) => {
          const d = snap.data() as any
          const uri = d?.assets?.overlay_uri
          if (uri) {
            unsub()
            fetchOverlayUrl(uri)
          }
        })
      }
    } finally {
      setOverlayBusy(false)
    }
  }

  async function fetchOverlayUrl(gsUri: string) {
    const token = await auth.currentUser?.getIdToken()
    const resp = await fetch(`${import.meta.env.VITE_API_BASE_URL}/signed-url`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      body: JSON.stringify({ gs_uri: gsUri })
    })
    if (resp.ok) {
      const body = await resp.json()
      setOverlayUrl(body.url)
    }
  }

  async function retry() {
    if (!sessionId) return
    const token = await auth.currentUser?.getIdToken()
    await fetch(`${import.meta.env.VITE_API_BASE_URL}/sessions/${sessionId}/retry`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` },
    })
  }

  if (!data) return <div className="p-4">Loading...</div>
  return (
    <div className="space-y-4">
      <div className="flex items-center space-x-2">
        <span className={`text-xs px-2 py-1 rounded ${status === 'COMPLETE' ? 'bg-green-100 text-green-700' : status === 'ERROR' ? 'bg-red-100 text-red-700' : 'bg-yellow-100 text-yellow-700'}`}>{status || 'UNKNOWN'}</span>
        {status && status !== 'COMPLETE' && status !== 'ERROR' && <span className="animate-spin inline-block w-3 h-3 border-2 border-current border-t-transparent rounded-full" />}
        {status === 'ERROR' && (
          <button className="text-xs text-blue-600" onClick={retry}>Retry</button>
        )}
      </div>
      <div className="text-3xl font-extrabold">{data.pqs?.total ?? '-'}</div>
      {data.pqs_v2 && (
        <span className="inline-block text-xs bg-indigo-100 text-indigo-700 px-2 py-1 rounded">PQS v2</span>
      )}
      <div className="bg-white rounded-lg p-3 shadow">
        <div className="text-sm text-gray-600 mb-2">Components</div>
        <div className="h-40">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData}>
              <XAxis dataKey="k" />
              <YAxis domain={[0, 200]} />
              <Bar dataKey="v" fill="#2563eb" radius={[4,4,0,0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {data.pqs_v2 && (
        <div className="bg-white rounded-lg p-3 shadow">
          <div className="text-sm text-gray-600 mb-2">PQS v2 Components</div>
          <div className="h-40">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartV2}>
                <XAxis dataKey="k" />
                <YAxis domain={[0, 200]} />
                <Bar dataKey="v" fill="#16a34a" radius={[4,4,0,0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-3 grid grid-cols-3 gap-3 text-sm">
            <div><div className="text-gray-500">Release angle</div><div className="font-semibold">{data.pqs_v2.metrics?.release_angle_deg?.toFixed?.(0)}°</div></div>
            <div><div className="text-gray-500">X-factor peak</div><div className="font-semibold">{data.pqs_v2.metrics?.x_factor_peak_deg?.toFixed?.(0)}°</div></div>
            <div><div className="text-gray-500">Chain order</div><div className="font-semibold">{data.pqs_v2.metrics?.chain_order_score?.toFixed?.(0)}</div></div>
          </div>
        </div>
      )}

      {data.coaching && (
        <div className="space-y-3">
          <div className="bg-amber-50 border border-amber-200 text-amber-900 p-3 rounded">
            <div className="font-semibold mb-1">Coaching Summary</div>
            <div className="text-sm">{data.coaching.summary}</div>
          </div>
          {!!(data.coaching.priority_fixes?.length) && (
            <div className="bg-white rounded p-3 shadow">
              <div className="font-medium mb-2">Priority Fixes</div>
              <ul className="space-y-2">
                {data.coaching.priority_fixes.map((f:any, i:number) => (
                  <li key={i} className="text-sm">
                    <span className="inline-block text-xs bg-gray-200 rounded px-2 py-0.5 mr-2">{f.phase}</span>
                    <span className="font-semibold">{f.issue}</span>: {f.tip}
                    <div className="text-gray-600">Why: {f.why}</div>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {!!(data.coaching.reinforce_strengths?.length) && (
            <div className="bg-white rounded p-3 shadow">
              <div className="font-medium mb-2">Reinforce Strengths</div>
              <ul className="list-disc pl-5 text-sm text-gray-700">
                {data.coaching.reinforce_strengths.map((s:any, i:number) => (
                  <li key={i}>{s.phase}: {s.strength}</li>
                ))}
              </ul>
            </div>
          )}
          {!!(data.coaching.drill_suggestions?.length) && (
            <div className="bg-white rounded p-3 shadow">
              <div className="font-medium mb-2">Drill Suggestions</div>
              <ul className="list-disc pl-5 text-sm text-blue-700">
                {data.coaching.drill_suggestions.map((d:any, i:number) => (
                  <li key={i}><a href={d.link} target="_blank" rel="noreferrer">{d.name}</a></li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      <button onClick={playBlurred} className="bg-blue-600 text-white rounded px-4 py-2">Play Blurred Video</button>
      {videoUrl && (
        <video controls className="w-full rounded" src={videoUrl}></video>
      )}

      <div className="flex items-center gap-3">
        <button onClick={generateOverlay} disabled={overlayBusy} className="bg-indigo-600 disabled:opacity-50 text-white rounded px-4 py-2">{overlayBusy ? 'Generating…' : 'Generate Coaching Video'}</button>
        <span className="text-xs text-gray-600">Tip: long‑press to save video</span>
      </div>
      {overlayUrl && (
        <video controls className="w-full rounded" src={overlayUrl}></video>
      )}

      {!!(data.pqs?.flags?.length) && (
        <div>
          <div className="font-medium">Flags</div>
          <ul className="list-disc pl-5 text-sm text-gray-700">
            {data.pqs.flags.map((f: string, i: number) => <li key={i}>{f}</li>)}
          </ul>
        </div>
      )}

      {!!(data.pqs?.notes?.length) && (
        <div>
          <div className="font-medium">Notes</div>
          <ul className="list-disc pl-5 text-sm text-gray-700">
            {data.pqs.notes.map((n: string, i: number) => <li key={i}>{n}</li>)}
          </ul>
        </div>
      )}
    </div>
  )
}


