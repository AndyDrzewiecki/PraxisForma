import { useState } from 'react'
import { auth, googleProvider } from '../firebase'
import { signInWithEmailAndPassword, signInWithPopup } from 'firebase/auth'

export function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string|undefined>()

  async function onEmailLogin(e: React.FormEvent) {
    e.preventDefault()
    try {
      await signInWithEmailAndPassword(auth, email, password)
    } catch (e: any) {
      setError(e.message)
    }
  }

  async function onGoogle() {
    try { await signInWithPopup(auth, googleProvider) } catch (e: any) { setError(e.message) }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="w-full max-w-sm bg-white rounded-xl p-6 shadow">
        <h1 className="text-xl font-bold mb-4">Sign in to ThrowPro</h1>
        {error && <div className="text-red-600 text-sm mb-2">{error}</div>}
        <form className="space-y-3" onSubmit={onEmailLogin}>
          <input className="w-full border rounded px-3 py-2" placeholder="Email" value={email} onChange={e=>setEmail(e.target.value)} />
          <input type="password" className="w-full border rounded px-3 py-2" placeholder="Password" value={password} onChange={e=>setPassword(e.target.value)} />
          <button className="w-full bg-blue-600 text-white rounded py-2">Sign in</button>
        </form>
        <div className="text-center text-sm my-3">or</div>
        <button className="w-full border rounded py-2" onClick={onGoogle}>Continue with Google</button>
      </div>
    </div>
  )
}


