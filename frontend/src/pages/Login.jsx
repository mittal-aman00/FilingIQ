import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { isLoggedIn, login } from '../lib/storage.js'
import './Login.css'

export default function Login() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')

  if (isLoggedIn()) return <Navigate to="/" replace />

  function handleSubmit(e) {
    e.preventDefault()
    setError('')
    if (!email.trim() || !password.trim()) {
      setError('Enter any email and password to continue.')
      return
    }
    // Mock auth — any credentials unlock the terminal
    login(email)
    navigate('/', { replace: true })
  }

  return (
    <div className="login">
      <div className="login__frame">
        <header className="login__brand">
          <div className="login__tick">FILINGIQ</div>
          <h1 className="login__title">NVIDIA 10-K Research Terminal</h1>
          <p className="login__sub">
            Equity filing intelligence — table-aware RAG over SEC Form 10-K
          </p>
        </header>

        <form className="login__form" onSubmit={handleSubmit} noValidate>
          <label className="login__label">
            <span>Analyst ID</span>
            <input
              type="email"
              autoComplete="username"
              placeholder="analyst@firm.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </label>
          <label className="login__label">
            <span>Access key</span>
            <input
              type="password"
              autoComplete="current-password"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          {error ? <p className="login__error">{error}</p> : null}
          <button type="submit" className="login__submit">
            Enter terminal
          </button>
          <p className="login__hint">Demo mode — any email / password unlocks access.</p>
        </form>

        <footer className="login__meta">
          <span>NVDA · FY2024–FY2026</span>
          <span className="login__amber">SECURE SESSION</span>
        </footer>
      </div>
    </div>
  )
}
