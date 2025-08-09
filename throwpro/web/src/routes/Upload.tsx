import { useRef, useState } from 'react'
import { auth } from '../firebase'
import { useNavigate } from 'react-router-dom'

export function Upload() {
  const inputRef = useRef<HTMLInputElement|null>(null)
  const [file, setFile] = useState<File|null>(null)
  const [error, setError] = useState<string|undefined>()
  const [progress, setProgress] = useState<number>(0)
  const [busy, setBusy] = useState<boolean>(false)
  const navigate = useNavigate()

  function onPick(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0] || null
    if (f) {
      if (!f.type.startsWith('video/')) { setError('Please select a video file'); return }
      if (f.size > 200 * 1024 * 1024) { setError('Max 200MB'); return }
      setError(undefined)
      setFile(f)
    }
  }

  async function onUpload() {
    if (!file) return
    setBusy(true)
    setProgress(0)
    try {
      const token = await auth.currentUser?.getIdToken()
      if (!token) { setError('Not signed in'); return }
      const initResp = await fetch(`${import.meta.env.VITE_API_BASE_URL}/uploads/init`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ filename: file.name, content_type: file.type || 'video/mp4' })
      })
      if (!initResp.ok) { setError('Failed to start upload'); return }
      const { upload_url, sessionId } = await initResp.json()

      await resumablePut(upload_url, file, (loaded, total) => setProgress(Math.round(loaded/total*100)))

      navigate(`/s/${sessionId}`)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  async function resumablePut(url: string, file: File, onProgress: (loaded: number, total: number) => void) {
    const chunkSize = 8 * 1024 * 1024 // 8MB
    let offset = 0
    const total = file.size
    while (offset < total) {
      const end = Math.min(offset + chunkSize, total)
      const chunk = file.slice(offset, end)
      const resp = await fetch(url, {
        method: 'PUT',
        headers: {
          'Content-Type': file.type || 'video/mp4',
          'Content-Range': `bytes ${offset}-${end-1}/${total}`
        },
        body: chunk
      })
      if (!(resp.status === 308 || resp.ok)) {
        throw new Error(`Upload failed (${resp.status})`)
      }
      offset = end
      onProgress(offset, total)
      // For 308, GCS returns Range header indicating received bytes; continue
    }
  }

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold">Upload a Throw</h2>
      {error && <div className="text-red-600 text-sm">{error}</div>}
      <div className="border-2 border-dashed rounded p-6 text-center">
        <input ref={inputRef} type="file" accept="video/*" className="hidden" onChange={onPick} />
        {!file && <button className="px-4 py-2 border rounded" onClick={() => inputRef.current?.click()}>Choose video</button>}
        {file && (
          <div className="space-y-2">
            <div className="text-sm">{file.name} ({Math.round(file.size/1024/1024)} MB)</div>
            <div className="w-full bg-gray-200 h-2 rounded">
              <div className="bg-blue-600 h-2 rounded" style={{ width: `${progress}%` }} />
            </div>
            <div className="flex space-x-2">
              <button disabled={busy} className="px-4 py-2 bg-blue-600 text-white rounded" onClick={onUpload}>{busy ? 'Uploading...' : 'Upload'}</button>
              <button disabled={busy} className="px-4 py-2 border rounded" onClick={() => { setFile(null); setProgress(0) }}>Clear</button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}



