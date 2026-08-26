/**
 * Browser persistence for mock auth + chat threads.
 *
 * Chat history lives in localStorage so it survives refresh after you clone
 * from GitHub. The repo itself does not write chat logs (browsers cannot
 * push to GitHub). Use export/import JSON if you want a seed file in the repo.
 */

const AUTH_KEY = 'filingiq.auth'
const CHATS_KEY = 'filingiq.chats'
const ACTIVE_KEY = 'filingiq.activeChatId'

export function isLoggedIn() {
  try {
    return Boolean(JSON.parse(localStorage.getItem(AUTH_KEY) || 'null')?.email)
  } catch {
    return false
  }
}

export function getSession() {
  try {
    return JSON.parse(localStorage.getItem(AUTH_KEY) || 'null')
  } catch {
    return null
  }
}

export function login(email) {
  const session = { email: email.trim() || 'analyst@demo.local', at: Date.now() }
  localStorage.setItem(AUTH_KEY, JSON.stringify(session))
  return session
}

export function logout() {
  localStorage.removeItem(AUTH_KEY)
}

export function loadChats() {
  try {
    const raw = JSON.parse(localStorage.getItem(CHATS_KEY) || '[]')
    return Array.isArray(raw) ? raw : []
  } catch {
    return []
  }
}

export function saveChats(chats) {
  localStorage.setItem(CHATS_KEY, JSON.stringify(chats))
}

export function getActiveChatId() {
  return localStorage.getItem(ACTIVE_KEY)
}

export function setActiveChatId(id) {
  if (id == null) localStorage.removeItem(ACTIVE_KEY)
  else localStorage.setItem(ACTIVE_KEY, id)
}

export function newChatId() {
  return `chat_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
}

/** Download chats as JSON (optional seed for the GitHub repo). */
export function exportChatsJson(chats) {
  const blob = new Blob([JSON.stringify(chats, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'filingiq-chats.json'
  a.click()
  URL.revokeObjectURL(url)
}
