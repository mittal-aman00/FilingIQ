import { useEffect, useRef, useState } from 'react'
import './ChatPanel.css'

export default function ChatPanel({
  chat,
  busy,
  error,
  suggestions,
  selectedMessageId,
  onAsk,
  onSelectMessage,
}) {
  const [draft, setDraft] = useState('')
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chat?.messages?.length, busy])

  function submit(e) {
    e?.preventDefault()
    if (!draft.trim() || busy) return
    const q = draft
    setDraft('')
    onAsk(q)
  }

  const empty = !chat?.messages?.length

  return (
    <section className="chat">
      <div className="chat__head">
        <h2 className="chat__title">{chat?.title || 'Research thread'}</h2>
        <span className="chat__tag">QUERY WINDOW</span>
      </div>

      <div className="chat__stream" role="log" aria-live="polite">
        {empty ? (
          <div className="chat__empty">
            <p className="chat__empty-lead">
              Ask anything disclosed in the ingested NVIDIA 10-K filings.
            </p>
            <div className="chat__suggestions">
              {suggestions.map((s) => (
                <button
                  key={s}
                  type="button"
                  className="chat__suggestion"
                  disabled={busy}
                  onClick={() => onAsk(s)}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          chat.messages.map((m) => (
            <article
              key={m.id}
              className={`chat__bubble chat__bubble--${m.role} ${
                m.role === 'assistant' && m.id === selectedMessageId ? 'is-selected' : ''
              }`}
              onClick={() => m.role === 'assistant' && onSelectMessage(m.id)}
            >
              <header className="chat__bubble-meta">
                <span>{m.role === 'user' ? 'ANALYST' : 'FILINGIQ'}</span>
                <span>{formatClock(m.at)}</span>
              </header>
              <pre className="chat__bubble-body">{m.content}</pre>
              {m.role === 'assistant' && m.payload ? (
                <div className="chat__bubble-flags">
                  <span className="chip">{m.payload.type || 'single'}</span>
                  {m.payload.verified != null ? (
                    <span className={`chip ${m.payload.verified ? 'chip--ok' : 'chip--warn'}`}>
                      {m.payload.verified ? 'VERIFIED' : 'UNVERIFIED'}
                    </span>
                  ) : null}
                  {m.payload.type === 'comparison' ? (
                    <span className="chip chip--amber">COMPARISON</span>
                  ) : null}
                </div>
              ) : null}
            </article>
          ))
        )}
        {busy ? (
          <div className="chat__thinking">
            <span className="chat__thinking-dot" />
            Retrieving filings · verifying numbers…
          </div>
        ) : null}
        <div ref={bottomRef} />
      </div>

      {error ? <div className="chat__error">{error}</div> : null}

      <form className="chat__composer" onSubmit={submit}>
        <textarea
          rows={2}
          placeholder="Ask about revenue, margins, notes, risks…"
          value={draft}
          disabled={busy}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              submit()
            }
          }}
        />
        <button type="submit" disabled={busy || !draft.trim()}>
          Ask
        </button>
      </form>
    </section>
  )
}

function formatClock(ts) {
  try {
    return new Date(ts).toLocaleTimeString(undefined, {
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return ''
  }
}
