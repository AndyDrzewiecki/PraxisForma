import { Outlet, Link, useNavigate } from 'react-router-dom'
import { auth } from '../firebase'
import { onAuthStateChanged, signOut } from 'firebase/auth'
import { useState, useEffect as _useEffect } from 'react'
import { useEffect } from 'react'

export function App() {
  const navigate = useNavigate()
  useEffect(() => {
    const unsub = onAuthStateChanged(auth, (u) => {
      if (!u) navigate('/login')
    })
    return () => unsub()
  }, [navigate])
  const [isAdmin, setIsAdmin] = useState<boolean>(false)
  _useEffect(() => {
    async function check() {
      if (!auth.currentUser) return
      const token = await auth.currentUser.getIdToken()
      const resp = await fetch(`${import.meta.env.VITE_API_BASE_URL}/admin/me`, { headers: { Authorization: `Bearer ${token}` } })
      if (resp.ok) { const body = await resp.json(); setIsAdmin(!!body.isAdmin) }
    }
    check()
  }, [])

  return (
    <div className="min-h-full max-w-xl mx-auto p-4 space-y-4">
      <header className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <Link to="/" className="font-bold text-xl">ThrowPro</Link>
          <Link to="/upload" className="text-sm text-blue-600">Upload</Link>
          <Link to="/progress" className="text-sm text-green-600">Progress</Link>
          {isAdmin && <Link to="/admin/calibration" className="text-sm text-indigo-600">Admin</Link>}
        </div>
        <button className="text-sm text-blue-600" onClick={() => signOut(auth)}>Sign out</button>
      </header>
      <Outlet />
    </div>
  )
}


