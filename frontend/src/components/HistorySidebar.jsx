import './HistorySidebar.css'

export default function HistorySidebar({
  chats,
  activeId,
  onNew,
  onSelect,
  onDelete,
  onExport,
}) {
  const sorted = [...chats].sort((a, b) => b.updatedAt - a.updatedAt)

  return (
    <aside className="sidebar">
      <div className="sidebar__head">
        <span className="sidebar__label">Threads</span>
        <button type="button" className="sidebar__new" onClick={onNew}>
          + New
        </button>
      </div>

      <nav className="sidebar__list" aria-label="Chat history">
        {sorted.map((chat) => (
          <div
            key={chat.id}
            className={`sidebar__item ${chat.id === activeId ? 'is-active' : ''}`}
          >
            <button
              type="button"
              className="sidebar__item-main"
              onClick={() => onSelect(chat.id)}
            >
              <span className="sidebar__item-title">{chat.title}</span>
              <span className="sidebar__item-meta">
                {chat.messages.length} msg · {formatTime(chat.updatedAt)}
              </span>
            </button>
            <button
              type="button"
              className="sidebar__item-del"
              title="Delete thread"
              onClick={() => onDelete(chat.id)}
            >
              ×
            </button>
          </div>
        ))}
      </nav>

      <div className="sidebar__foot">
        <p className="sidebar__corp">
          Corpus: <strong>NVDA</strong> 10-K
          <br />
          FY2024 · FY2025 · FY2026
        </p>
        <button type="button" className="sidebar__export" onClick={onExport}>
          Export history JSON
        </button>
      </div>
    </aside>
  )
}

function formatTime(ts) {
  try {
    return new Date(ts).toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return ''
  }
}
