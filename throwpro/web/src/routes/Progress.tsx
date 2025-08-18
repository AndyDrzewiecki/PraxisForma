import { useEffect, useMemo, useState } from 'react'
import { auth, db } from '../firebase'
import { collection, query, where, orderBy, onSnapshot } from 'firebase/firestore'
import { Link } from 'react-router-dom'
import { LineChart, Line, XAxis, YAxis, ResponsiveContainer, Tooltip } from 'recharts'

type Item = {
  id: string
  created_at?: any
  pqs_v2?: any
}

export function Progress() {
  const [items, setItems] = useState<Item[]>([])
  useEffect(() => {
    const u = auth.currentUser
    if (!u) return
    const q = query(
      collection(db, 'throwSessions'),
      where('userId', '==', u.uid),
      orderBy('created_at', 'asc')
    )
    const unsub = onSnapshot(q, (snap) => {
      const arr: Item[] = []
      snap.forEach((d) => arr.push({ id: d.id, ...(d.data() as any) }))
      setItems(arr)
    })
    return () => unsub()
  }, [])

  const points = useMemo(() => {
    return items.map((it) => {
      const m = it.pqs_v2?.metrics || {}
      return {
        id: it.id,
        when: it.created_at?.toDate ? it.created_at.toDate() : null,
        total: it.pqs_v2?.total ?? null,
        release_angle_deg: m.release_angle_deg ?? null,
        chain_order_score: m['chain_order_score'] ?? null,
        v_hand_peak_norm: m['v_hand_peak_norm'] ?? null,
      }
    })
  }, [items])

  return (
    <div className="space-y-3">
      <h2 className="text-lg font-semibold">Progress</h2>
      <div className="space-y-2">
        {points.length === 0 && (
          <div className="text-sm text-gray-600">No sessions yet — upload your first throw.</div>
        )}
        {!!points.length && (
          <div className="grid grid-cols-1 gap-3">
            <Spark title="Total" dataKey="total" points={points} color="#1e88e5" />
            <Spark title="Release angle" dataKey="release_angle_deg" points={points} color="#43a047" />
            <Spark title="Chain order" dataKey="chain_order_score" points={points} color="#8e24aa" />
            <Spark title="v_hand peak" dataKey="v_hand_peak_norm" points={points} color="#fb8c00" />
          </div>
        )}
        {points.map(p => (
          <div key={p.id} className="bg-white rounded shadow p-3 flex items-center justify-between">
            <div>
              <div className="text-sm text-gray-600">{p.when ? p.when.toLocaleDateString() : ''}</div>
              <div className="text-xs text-gray-500">release_angle={p.release_angle_deg ?? '-'}°, chain={p.chain_order_score ?? '-'}, v_hand={p.v_hand_peak_norm ?? '-'}</div>
            </div>
            <div className="flex items-center gap-3">
              <div className="text-xl font-bold">{p.total ?? '-'}</div>
              <Link to={`/s/${p.id}`} className="text-blue-600 text-sm">View</Link>
              <Link to={`/compare?a=${p.id}`} className="text-indigo-600 text-sm">Compare</Link>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function Spark({ title, dataKey, points, color }:{ title: string, dataKey: string, points: any[], color: string }) {
  const data = points.map(p => ({ x: p.when ? p.when.getTime?.() || 0 : 0, y: (p as any)[dataKey] ?? null }))
  return (
    <div className="bg-white rounded shadow p-3">
      <div className="text-sm text-gray-700 mb-1">{title}</div>
      <div className="h-20">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <XAxis dataKey="x" hide />
            <YAxis hide />
            <Tooltip />
            <Line type="monotone" dataKey="y" stroke={color} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}


