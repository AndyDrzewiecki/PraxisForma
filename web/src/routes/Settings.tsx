import { useEffect, useState } from 'react'
import { auth, db } from '../firebase'
import { doc, getDoc, setDoc, serverTimestamp } from 'firebase/firestore'

export function Settings() {
  const [form, setForm] = useState<any>({ event: 'discus', ageBand: 'Open', sex: 'M', handedness: 'right' })
  const [saved, setSaved] = useState('')
  useEffect(() => {
    async function load() {
      const uid = auth.currentUser?.uid
      if (!uid) return
      const snap = await getDoc(doc(db, 'athleteProfiles', uid))
      if (snap.exists()) setForm({ ...form, ...(snap.data() as any) })
    }
    load()
  }, [])
  async function save() {
    const uid = auth.currentUser?.uid
    if (!uid) return
    await setDoc(doc(db, 'athleteProfiles', uid), { ...form, updated_at: serverTimestamp() }, { merge: true })
    setSaved('Saved')
    setTimeout(()=>setSaved(''), 1500)
  }
  return (
    <div className="space-y-3">
      <h2 className="text-lg font-semibold">Athlete Settings</h2>
      {saved && <div className="text-sm text-green-700">{saved}</div>}
      <div className="grid grid-cols-2 gap-2">
        <select value={form.event} onChange={e=>setForm((f:any)=>({...f,event:e.target.value}))}>
          {['discus','shot_put_rotational','shot_put_glide'].map(v=> <option key={v} value={v}>{v}</option>)}
        </select>
        <select value={form.ageBand} onChange={e=>setForm((f:any)=>({...f,ageBand:e.target.value}))}>
          {['U14','U16','U18','U20','Open'].map(v=> <option key={v} value={v}>{v}</option>)}
        </select>
        <select value={form.sex} onChange={e=>setForm((f:any)=>({...f,sex:e.target.value}))}>
          {['M','F'].map(v=> <option key={v} value={v}>{v}</option>)}
        </select>
        <select value={form.handedness} onChange={e=>setForm((f:any)=>({...f,handedness:e.target.value}))}>
          {['left','right'].map(v=> <option key={v} value={v}>{v}</option>)}
        </select>
      </div>
      <button className="px-4 py-2 bg-blue-600 text-white rounded" onClick={save}>Save</button>
    </div>
  )
}






