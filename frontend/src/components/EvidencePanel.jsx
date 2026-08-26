import './EvidencePanel.css'

export default function EvidencePanel({ message }) {
  const payload = message?.payload

  if (!payload) {
    return (
      <aside className="evidence">
        <div className="evidence__head">
          <span className="evidence__label">Evidence</span>
        </div>
        <div className="evidence__empty">
          Select an assistant reply to inspect intent, citations, verification, and
          comparison math.
        </div>
      </aside>
    )
  }

  const isComparison = payload.type === 'comparison'
  const intent = payload.intent
  const citations = collectCitations(payload)
  const years = collectYears(payload)

  return (
    <aside className="evidence">
      <div className="evidence__head">
        <span className="evidence__label">Evidence</span>
        <span className="evidence__type">{(payload.type || 'single').toUpperCase()}</span>
      </div>

      <div className="evidence__scroll">
        {/* Verified + fiscal year chips */}
        <section className="evidence__block">
          <h3 className="evidence__h">Status</h3>
          <div className="evidence__row">
            {payload.verified != null ? (
              <span className={`badge ${payload.verified ? 'badge--ok' : 'badge--warn'}`}>
                {payload.verified ? '✓ Verified numbers' : '⚠ Unverified'}
              </span>
            ) : (
              <span className="badge badge--muted">Verification N/A (comparison path)</span>
            )}
          </div>
          {years.length ? (
            <div className="evidence__chips">
              {years.map((y) => (
                <span key={y} className="fy-chip">
                  FY{y}
                </span>
              ))}
            </div>
          ) : null}
        </section>

        {/* Intent transparency */}
        {intent ? (
          <section className="evidence__block">
            <h3 className="evidence__h">Interpreted intent</h3>
            <dl className="evidence__dl">
              <div>
                <dt>Type</dt>
                <dd>{intent.question_type}</dd>
              </div>
              <div>
                <dt>Metric</dt>
                <dd className="mono">{intent.metric || '—'}</dd>
              </div>
              <div>
                <dt>Years</dt>
                <dd className="mono">
                  {(intent.fiscal_years || []).length
                    ? intent.fiscal_years.join(', ')
                    : '—'}
                </dd>
              </div>
              <div>
                <dt>Section hint</dt>
                <dd>{intent.section_hint || '—'}</dd>
              </div>
              <div>
                <dt>Needs table</dt>
                <dd>{String(intent.needs_table)}</dd>
              </div>
              <div>
                <dt>Requires calc</dt>
                <dd>{String(intent.requires_calculation)}</dd>
              </div>
            </dl>
          </section>
        ) : null}

        {/* Comparison delta */}
        {isComparison && payload.delta ? (
          <section className="evidence__block">
            <h3 className="evidence__h">Verified arithmetic</h3>
            <div className="evidence__delta">
              <div>
                <span className="muted">Later</span>
                <strong className="mono amber">{payload.delta.later}</strong>
              </div>
              <div>
                <span className="muted">Earlier</span>
                <strong className="mono">{payload.delta.earlier}</strong>
              </div>
              <div>
                <span className="muted">Δ Absolute</span>
                <strong className="mono amber">{payload.delta.delta}</strong>
              </div>
              <div>
                <span className="muted">Δ %</span>
                <strong className="mono amber">
                  {payload.delta.pct_change != null
                    ? `${payload.delta.pct_change}%`
                    : '—'}
                </strong>
              </div>
            </div>
          </section>
        ) : null}

        {/* Sub-answers for comparison */}
        {isComparison && payload.sub_answers?.length ? (
          <section className="evidence__block">
            <h3 className="evidence__h">Per-year sub-answers</h3>
            <ul className="evidence__subs">
              {payload.sub_answers.map((s) => (
                <li key={s.year}>
                  <div className="evidence__sub-head">
                    <span className="fy-chip">FY{s.year}</span>
                    {s.extracted_figure ? (
                      <span className="mono amber">{s.extracted_figure}</span>
                    ) : null}
                  </div>
                  <p>{s.answer}</p>
                  {s.citations?.length ? (
                    <ul className="evidence__cites">
                      {s.citations.map((c, i) => (
                        <li key={`${s.year}-${i}`}>{formatCite(c)}</li>
                      ))}
                    </ul>
                  ) : null}
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {/* Single-path answer echo */}
        {!isComparison && payload.answer ? (
          <section className="evidence__block">
            <h3 className="evidence__h">Answer</h3>
            <p className="evidence__answer">{payload.answer}</p>
          </section>
        ) : null}

        {/* Citations */}
        <section className="evidence__block">
          <h3 className="evidence__h">Citations</h3>
          {citations.length ? (
            <ul className="evidence__cites evidence__cites--main">
              {citations.map((c, i) => (
                <li key={i}>
                  <button type="button" className="cite-btn">
                    {formatCite(c)}
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">No structured citations returned.</p>
          )}
        </section>

        {/* Raw payload for power users / debugging demos */}
        <section className="evidence__block">
          <h3 className="evidence__h">Raw payload</h3>
          <pre className="evidence__raw">{JSON.stringify(payload, null, 2)}</pre>
        </section>
      </div>
    </aside>
  )
}

function formatCite(c) {
  if (!c) return '—'
  const fy = c.fiscal_year ?? '?'
  const page = c.page ?? '?'
  const section = c.section || 'Section'
  return `[FY${fy}, p.${page}, ${section}]`
}

function collectCitations(payload) {
  if (payload.type === 'comparison') {
    return (payload.sub_answers || []).flatMap((s) => s.citations || [])
  }
  return payload.citations || []
}

function collectYears(payload) {
  if (payload.intent?.fiscal_years?.length) return payload.intent.fiscal_years
  if (payload.type === 'comparison') {
    return (payload.sub_answers || []).map((s) => s.year).filter(Boolean)
  }
  const fromCites = (payload.citations || [])
    .map((c) => c.fiscal_year)
    .filter(Boolean)
  return [...new Set(fromCites)]
}
