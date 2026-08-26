import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import HistorySidebar from '../components/HistorySidebar.jsx'
import ChatPanel from '../components/ChatPanel.jsx'
import EvidencePanel from '../components/EvidencePanel.jsx'
import { askQuestion, checkHealth } from '../lib/api.js'
import {
  exportChatsJson,
  getActiveChatId,
  getSession,
  loadChats,
  logout,
  newChatId,
  saveChats,
  setActiveChatId,
} from '../lib/storage.js'
import './Workspace.css'

const SUGGESTIONS = [
  'What was NVIDIA total revenue in fiscal year 2025?',
  'How did operating income change from FY2024 to FY2025?',
  'What risks does management flag around export controls?',
  'What does Note 14 say about goodwill?',
]

function emptyChat() {
  return {
    id: newChatId(),
    title: 'New research thread',
    createdAt: Date.now(),
    updatedAt: Date.now(),
    messages: [],
  }
}

export default function Workspace() {
  const navigate = useNavigate()
  const session = getSession()

  const [chats, setChats] = useState(() => {
    const existing = loadChats()
    if (existing.length) return existing
    const first = emptyChat()
    saveChats([first])
    setActiveChatId(first.id)
    return [first]
  })

  const [activeId, setActiveId] = useState(() => {
    const saved = getActiveChatId()
    if (saved && chats.some((c) => c.id === saved)) return saved
    return chats[0]?.id
  })

  const [selectedMessageId, setSelectedMessageId] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [health, setHealth] = useState(null)

  const activeChat = useMemo(
    () => chats.find((c) => c.id === activeId) || chats[0],
    [chats, activeId],
  )

  const selectedMessage = useMemo(() => {
    if (!activeChat) return null
    const assistants = activeChat.messages.filter((m) => m.role === 'assistant')
    if (!assistants.length) return null
    if (selectedMessageId) {
      return assistants.find((m) => m.id === selectedMessageId) || assistants.at(-1)
    }
    return assistants.at(-1)
  }, [activeChat, selectedMessageId])

  useEffect(() => {
    saveChats(chats)
  }, [chats])

  useEffect(() => {
    if (activeId) setActiveChatId(activeId)
  }, [activeId])

  useEffect(() => {
    checkHealth()
      .then(setHealth)
      .catch(() => setHealth({ status: 'offline', fiscal_years_loaded: [] }))
  }, [])

  const persistChats = useCallback((updater) => {
    setChats((prev) => {
      const next = typeof updater === 'function' ? updater(prev) : updater
      saveChats(next)
      return next
    })
  }, [])

  function handleNewChat() {
    const chat = emptyChat()
    persistChats((prev) => [chat, ...prev])
    setActiveId(chat.id)
    setSelectedMessageId(null)
    setError('')
  }

  function handleSelectChat(id) {
    setActiveId(id)
    setSelectedMessageId(null)
    setError('')
  }

  function handleDeleteChat(id) {
    persistChats((prev) => {
      const next = prev.filter((c) => c.id !== id)
      if (!next.length) {
        const chat = emptyChat()
        setActiveId(chat.id)
        return [chat]
      }
      if (id === activeId) setActiveId(next[0].id)
      return next
    })
    setSelectedMessageId(null)
  }

  function handleLogout() {
    logout()
    navigate('/login', { replace: true })
  }

  async function handleAsk(question) {
    const q = question.trim()
    if (!q || busy || !activeChat) return

    setBusy(true)
    setError('')

    const userMsg = {
      id: `m_${Date.now()}_u`,
      role: 'user',
      content: q,
      at: Date.now(),
    }

    persistChats((prev) =>
      prev.map((c) => {
        if (c.id !== activeChat.id) return c
        const title =
          c.messages.length === 0
            ? q.length > 48
              ? `${q.slice(0, 48)}…`
              : q
            : c.title
        return {
          ...c,
          title,
          updatedAt: Date.now(),
          messages: [...c.messages, userMsg],
        }
      }),
    )

    try {
      const data = await askQuestion(q)
      const assistantMsg = {
        id: `m_${Date.now()}_a`,
        role: 'assistant',
        content: formatAnswerText(data),
        at: Date.now(),
        payload: data,
      }
      persistChats((prev) =>
        prev.map((c) =>
          c.id === activeChat.id
            ? {
                ...c,
                updatedAt: Date.now(),
                messages: [...c.messages, assistantMsg],
              }
            : c,
        ),
      )
      setSelectedMessageId(assistantMsg.id)
    } catch (err) {
      setError(err.message || 'Request failed. Is the API running on :8000?')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="workspace">
      <header className="workspace__top">
        <div className="workspace__brand">
          <span className="workspace__logo">FILINGIQ</span>
          <span className="workspace__sep">/</span>
          <span className="workspace__product">NVDA 10-K TERMINAL</span>
        </div>
        <div className="workspace__status">
          <span
            className={`workspace__dot ${
              health?.status === 'ok' ? 'is-live' : 'is-down'
            }`}
          />
          <span className="workspace__api">
            {health?.status === 'ok'
              ? `API LIVE · FY ${ (health.fiscal_years_loaded || []).join(' · ') || '—' }`
              : 'API OFFLINE · localhost:8000'}
          </span>
          <span className="workspace__user">{session?.email}</span>
          <button type="button" className="workspace__ghost" onClick={handleLogout}>
            Sign out
          </button>
        </div>
      </header>

      <div className="workspace__body">
        <HistorySidebar
          chats={chats}
          activeId={activeChat?.id}
          onNew={handleNewChat}
          onSelect={handleSelectChat}
          onDelete={handleDeleteChat}
          onExport={() => exportChatsJson(chats)}
        />

        <ChatPanel
          chat={activeChat}
          busy={busy}
          error={error}
          suggestions={SUGGESTIONS}
          selectedMessageId={selectedMessage?.id}
          onAsk={handleAsk}
          onSelectMessage={setSelectedMessageId}
        />

        <EvidencePanel message={selectedMessage} />
      </div>
    </div>
  )
}

/** Flatten API payloads into readable chat bubble text. */
function formatAnswerText(data) {
  if (!data) return 'No response.'
  if (data.type === 'comparison') {
    const lines = (data.sub_answers || []).map(
      (s) => `FY${s.year}: ${s.answer}${s.extracted_figure ? ` [${s.extracted_figure}]` : ''}`,
    )
    if (data.delta) {
      lines.push(
        `Δ ${data.delta.delta} (${data.delta.pct_change != null ? `${data.delta.pct_change}%` : 'n/a'})`,
      )
    }
    return lines.join('\n\n')
  }
  return data.answer || JSON.stringify(data, null, 2)
}
