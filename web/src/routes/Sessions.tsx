import { useEffect, useState } from 'react'
import { auth, db } from '../firebase'
import { collection, query, where, orderBy, onSnapshot } from 'firebase/firestore'
import { Link } from 'react-router-dom'

type Session = {
  id: string
  userId: string
  blurred_uri?: string
  created_at?: any
  pqs?: { total: number }
}

export function Sessions() {
  const [sessions, setSessions] = useState<Session[]>([])
  useEffect(() => {
    const user = auth.currentUser
    if (!user) return
    const q = query(
      collection(db, 'throwSessions'),
      where('userId', '==', user.uid),
      orderBy('created_at', 'desc')
    )
    const unsub = onSnapshot(q, (snap) => {
      const items: Session[] = []
      snap.forEach((doc) => items.push({ id: doc.id, ...(doc.data() as any) }))
      setSessions(items)
    })
    return () => unsub()
  }, [])

  return (
    <div className="space-y-3">
      <h2 className="text-lg font-semibold">Your Sessions</h2>
      <div className="space-y-2">
        {sessions.map(s => {
          const filename = s.blurred_uri?.split('/').pop() || s.id
          const when = s.created_at?.toDate ? s.created_at.toDate().toLocaleString() : ''
          return (
            <div key={s.id} className="bg-white rounded-lg shadow p-3 flex items-center justify-between">
              <div>
                <div className="font-medium">{filename}</div>
                <div className="text-sm text-gray-600">{when}</div>
              </div>
              <div className="flex items-center space-x-3">
                <div className="text-xl font-bold">{s.pqs?.total ?? '-'}</div>
                <Link to={`/s/${s.id}`} className="text-blue-600 text-sm">View</Link>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}


