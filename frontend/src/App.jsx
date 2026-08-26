/**
 * FilingIQ frontend — Bloomberg-style research terminal.
 *
 * Routes:
 *   /login  — mock auth (any email/password)
 *   /       — 3-panel workspace (history | chat | evidence)
 */
import { Navigate, Route, Routes } from 'react-router-dom'
import Login from './pages/Login.jsx'
import Workspace from './pages/Workspace.jsx'
import { isLoggedIn } from './lib/storage.js'

function PrivateRoute({ children }) {
  return isLoggedIn() ? children : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/"
        element={
          <PrivateRoute>
            <Workspace />
          </PrivateRoute>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
