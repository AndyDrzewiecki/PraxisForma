import React from 'react'
import ReactDOM from 'react-dom/client'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import './index.css'
import { App } from './routes/App'
import { Login } from './routes/Login'
import { Sessions } from './routes/Sessions'
import { Upload } from './routes/Upload'
import { SessionDetail } from './routes/SessionDetail'
import { Settings } from './routes/Settings'
import { AdminCalibration } from './routes/AdminCalibration'

const router = createBrowserRouter([
  { path: '/login', element: <Login /> },
  { path: '/', element: <App />, children: [
      { index: true, element: <Sessions /> },
      { path: 'upload', element: <Upload /> },
      { path: 's/:sessionId', element: <SessionDetail /> },
      { path: 'settings', element: <Settings /> },
      { path: 'admin/calibration', element: <AdminCalibration /> },
    ] },
])

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>
)


