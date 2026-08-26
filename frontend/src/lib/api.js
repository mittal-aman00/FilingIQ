/** API client — FilingIQ FastAPI backend (default http://localhost:8000) */

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export async function checkHealth() {
  const res = await fetch(`${API_BASE}/health`)
  if (!res.ok) throw new Error(`Health check failed (${res.status})`)
  return res.json()
}

/**
 * POST /ask
 * Returns either:
 *   { type: 'single', intent, answer, verified, citations }
 *   { type: 'comparison', sub_answers, delta }
 */
export async function askQuestion(question) {
  const res = await fetch(`${API_BASE}/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  })
  if (!res.ok) {
    let detail = ''
    try {
      const data = await res.json()
      detail = data.detail || data.error || JSON.stringify(data)
    } catch {
      detail = await res.text().catch(() => '')
    }
    throw new Error(detail || `Request failed (${res.status})`)
  }
  return res.json()
}

export { API_BASE }
