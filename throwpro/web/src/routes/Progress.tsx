import { useEffect, useMemo, useState } from 'react'
import { auth, db } from '../firebase'
import { collection, query, where, orderBy, onSnapshot } from 'firebase/firestore'
import { Link } from 'react-router-dom'

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
        {points.map(p => (
          <div key={p.id} className="bg-white rounded shadow p-3 flex items-center justify-between">
            <div>
              <div className="text-sm text-gray-600">{p.when ? p.when.toLocaleDateString() : ''}</div>
              <div className="text-xs text-gray-500">release_angle={p.release_angle_deg ?? '-'}°, chain={p.chain_order_score ?? '-'}, v_hand={p.v_hand_peak_norm ?? '-'}</div>
            </div>
            <div className="flex items-center gap-3">
              <div className="text-xl font-bold">{p.total ?? '-'}</div>
              <Link to={`/s/${p.id}`} className="text-blue-600 text-sm">View</Link>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}


