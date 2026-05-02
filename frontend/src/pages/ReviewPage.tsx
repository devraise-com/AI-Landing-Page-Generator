import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useSession } from '../store/session.tsx'
import { parseSection, generatePage } from '../api/client'
import { isApiError } from '../api/errors'
import type { Section } from '../types/api'
import PlanCard from '../components/PlanCard'
import Popup from '../components/Popup'
import { debugError, debugLog } from '../utils/debug'
import styles from './ReviewPage.module.css'

// ── Serialise section → textarea text ─────────────────────────

function sectionToText(section: Section): string {
  const lines: string[] = []
  for (const [key, raw] of Object.entries(section.fields)) {
    const label = key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
    if (Array.isArray(raw)) {
      const serialised = raw
        .slice(0, 6)
        .map(item => {
          if (typeof item === 'string') return item
          if (typeof item === 'object' && item !== null) {
            return Object.entries(item as Record<string, unknown>)
              .map(([k, v]) => `${k}: ${v}`)
              .join(', ')
          }
          return String(item)
        })
        .join('\n  - ')
      lines.push(`${label}:\n  - ${serialised}`)
    } else if (typeof raw === 'object' && raw !== null) {
      const serialised = Object.entries(raw as Record<string, unknown>)
        .map(([k, v]) => `${k.replace(/_/g, ' ')}: ${v}`)
        .join('; ')
      lines.push(`${label}: ${serialised}`)
    } else {
      lines.push(`${label}: ${String(raw)}`)
    }
  }
  if (section.visual_direction) {
    lines.push(`Visual: ${section.visual_direction}`)
  }
  return lines.join('\n')
}

// ── Error helpers ─────────────────────────────────────────────

function apiErrorMessage(err: unknown): string {
  if (isApiError(err)) {
    if (err.status === 400) return err.message
    if (err.status === 401) return 'Access error — token is missing or invalid.'
    if (err.status === 429) return 'Rate limit reached. Please try again shortly.'
    return err.message || 'Something went wrong. Please try again.'
  }
  return 'Network error. Please check your connection and try again.'
}

// ── Icons ─────────────────────────────────────────────────────

function BackArrow() {
  return (
    <svg viewBox="0 0 12 12" fill="none" width="12" height="12" aria-hidden="true">
      <path d="M7.5 2L3.5 6l4 4" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

// ── Component ─────────────────────────────────────────────────

type View = 'list' | 'edit'
type GenerateStatus = 'idle' | 'loading' | 'error'
type SaveStatus = 'idle' | 'loading' | 'error'

export default function ReviewPage() {
  const navigate = useNavigate()
  const { landingPlan, setLandingPlan, setFinalPage } = useSession()

  // Redirect if no plan in session
  useEffect(() => {
    if (!landingPlan) {
      debugLog('review-page', 'redirect.no_landing_plan')
      navigate('/new', { replace: true })
    }
  }, [landingPlan, navigate])

  // ── Local sections state (syncs to session on mutations) ──
  const [sections, setSections] = useState<Section[]>(
    () => landingPlan?.sections.slice() ?? [],
  )
  const [removingIds, setRemovingIds] = useState<Set<string>>(new Set())

  // ── View state ────────────────────────────────────────────
  const [view, setView] = useState<View>('list')
  const [editIdx, setEditIdx] = useState(0)
  const [editText, setEditText] = useState('')
  const [editSnapshot, setEditSnapshot] = useState('')

  // ── Popup / network state ─────────────────────────────────
  const [showSavePopup, setShowSavePopup] = useState(false)
  const [saveStatus, setSaveStatus] = useState<SaveStatus>('idle')
  const [saveError, setSaveError] = useState('')
  const [generateStatus, setGenerateStatus] = useState<GenerateStatus>('idle')
  const [generateError, setGenerateError] = useState('')

  // ── Helpers ───────────────────────────────────────────────

  const persistSections = useCallback(
    (next: Section[]) => {
      setSections(next)
      setLandingPlan({ sections: next })
    },
    [setLandingPlan],
  )

  const currentSection = sections[editIdx]

  // ── Handlers: list view ───────────────────────────────────

  function handleDelete(id: string) {
    debugLog('review-page', 'section.delete.start', { sectionId: id })
    setRemovingIds(prev => new Set(prev).add(id))
    setTimeout(() => {
      setSections(latest => {
        const next = latest.filter(s => s.id !== id)
        setLandingPlan({ sections: next })
        debugLog('review-page', 'section.delete.done', {
          sectionId: id,
          sectionsCount: next.length,
        })
        return next
      })
      setRemovingIds(prev => {
        const s = new Set(prev)
        s.delete(id)
        return s
      })
    }, 200)
  }

  function handleEnterEdit(idx: number) {
    const text = sectionToText(sections[idx])
    setEditIdx(idx)
    setEditText(text)
    setEditSnapshot(text)
    setView('edit')
  }

  function handleEditPrompt() {
    navigate('/new')
  }

  // ── Handlers: edit view ───────────────────────────────────

  function handleExitEdit() {
    setSaveStatus('idle')
    setSaveError('')
    setView('list')
  }

  function handleUndo() {
    handleExitEdit()
  }

  function handleSaveClick() {
    if (editText === editSnapshot) {
      handleExitEdit()
      return
    }
    setSaveStatus('idle')
    setSaveError('')
    setShowSavePopup(true)
  }

  function handleSidebarSwitch(idx: number) {
    const text = sectionToText(sections[idx])
    setEditIdx(idx)
    setEditText(text)
    setEditSnapshot(text)
  }

  // ── Handler: re-parse section (Call 1b) ───────────────────

  async function handleRegenerate() {
    if (!currentSection) return
    debugLog('review-page', 'section.regenerate.start', {
      sectionId: currentSection.id,
      sectionType: currentSection.type,
      textLength: editText.length,
    })
    setSaveStatus('loading')
    setSaveError('')
    try {
      const updated = await parseSection(currentSection.id, editText, currentSection.type)
      const next = sections.map((s, i) => (i === editIdx ? updated : s))
      debugLog('review-page', 'section.regenerate.success', {
        sectionId: currentSection.id,
        sectionsCount: next.length,
      })
      persistSections(next)
      setShowSavePopup(false)
      setSaveStatus('idle')
      handleExitEdit()
    } catch (err) {
      debugError('review-page', 'section.regenerate.failed', err)
      setSaveStatus('error')
      setSaveError(apiErrorMessage(err))
    }
  }

  // ── Handler: generate page (Call 2) ──────────────────────

  async function handleGenerate() {
    debugLog('review-page', 'page.generate.start', { sectionsCount: sections.length })
    setGenerateStatus('loading')
    setGenerateError('')
    try {
      const result = await generatePage({ sections })
      debugLog('review-page', 'page.generate.success', { htmlLength: result.html.length })
      setFinalPage({ html: result.html })
      navigate('/preview')
    } catch (err) {
      debugError('review-page', 'page.generate.failed', err)
      setGenerateStatus('error')
      setGenerateError(apiErrorMessage(err))
    }
  }

  // ── Render ────────────────────────────────────────────────

  const isOverlayOpen = generateStatus !== 'idle'

  if (!landingPlan) return null // while redirecting

  return (
    <div className={styles.root}>
      {/* Content layer */}
      <div className={`${styles.pageContent} ${isOverlayOpen ? styles.blurred : ''}`}>
        <nav className="top-nav">
          <span className="nav-logo">Landing Builder</span>
        </nav>

        <div className={styles.shell}>
          {view === 'list' ? (
            /* ──────── SCREEN 3.1 – VIEW MODE ──────── */
            <>
              <div className={styles.listHeader}>
                <h2>Landing plan</h2>
              </div>

              <div className={styles.cardsArea}>
                {sections.length === 0 ? (
                  <div className={styles.emptyState}>
                    <p>All sections deleted.</p>
                    <button
                      type="button"
                      className="btn-ghost"
                      onClick={handleEditPrompt}
                    >
                      Start over
                    </button>
                  </div>
                ) : (
                  sections.map((s, idx) => (
                    <PlanCard
                      key={s.id}
                      section={s}
                      removing={removingIds.has(s.id)}
                      onEdit={() => handleEnterEdit(idx)}
                      onDelete={() => handleDelete(s.id)}
                    />
                  ))
                )}
              </div>

              <div className={styles.footer}>
                <button
                  type="button"
                  className="btn-primary"
                  disabled={sections.length === 0}
                  onClick={handleGenerate}
                >
                  Approve &amp; generate page
                </button>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={handleEditPrompt}
                >
                  Edit prompt
                </button>
              </div>
            </>
          ) : (
            /* ──────── SCREEN 3.2 – EDIT MODE ──────── */
            <>
              <button type="button" className={styles.backLink} onClick={handleExitEdit}>
                <BackArrow /> Back to plan
              </button>

              <div className={styles.editArea}>
                {/* Sidebar (desktop only) */}
                <div className={styles.sidebar}>
                  <div className={styles.sidebarTitle}>Sections</div>
                  {sections.map((s, idx) => (
                    <button
                      key={s.id}
                      type="button"
                      className={`${styles.sidebarItem} ${idx === editIdx ? styles.sidebarItemActive : ''}`}
                      onClick={() => handleSidebarSwitch(idx)}
                    >
                      {s.name}
                    </button>
                  ))}
                </div>

                {/* Main editor */}
                {currentSection && (
                  <div className={styles.editMain}>
                    <div className={styles.editCard}>
                      <div className={styles.editCardHead}>
                        <span className={styles.editCardName}>{currentSection.name}</span>
                        <span className={styles.editCardTag}>{currentSection.type}</span>
                      </div>
                      <div className={styles.editCardBody}>
                        <textarea
                          className={styles.editTextarea}
                          value={editText}
                          onChange={e => setEditText(e.target.value)}
                        />
                        <div className={styles.editHint}>
                          Edit in free text — AI will parse each field and redraw the card on save.
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              <div className={styles.footer}>
                <button
                  type="button"
                  className="btn-primary"
                  onClick={handleSaveClick}
                >
                  Save changes
                </button>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={handleUndo}
                >
                  Undo
                </button>
              </div>
            </>
          )}
        </div>
      </div>

      {/* ── SCREEN 3.3 – SAVE POPUP ── */}
      {showSavePopup && (
        <Popup onClose={saveStatus === 'idle' ? () => setShowSavePopup(false) : undefined}>
          {saveStatus === 'loading' ? (
            <div className={styles.generateOverlay}>
              <div className="spinner" />
              <div className={styles.generateTitle}>Updating section...</div>
            </div>
          ) : (
            <>
              <div className={styles.saveTitle}>Apply changes?</div>
              <div className={styles.saveSub}>
                AI will re-generate the <strong>{currentSection?.name}</strong> section based on your edits.
                This takes a few seconds.
              </div>
              <div className={styles.saveFooter}>
                <button
                  type="button"
                  className="btn-primary"
                  onClick={handleRegenerate}
                >
                  Update
                </button>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => {
                    setShowSavePopup(false)
                    setSaveStatus('idle')
                    setSaveError('')
                  }}
                >
                  Cancel
                </button>
              </div>
              {saveStatus === 'error' && (
                <div className={styles.saveError}>{saveError}</div>
              )}
            </>
          )}
        </Popup>
      )}

      {/* ── GENERATE PAGE OVERLAY ── */}
      {generateStatus === 'loading' && (
        <Popup>
          <div className={styles.generateOverlay}>
            <div className="spinner" />
            <div className={styles.generateTitle}>Generating your page...</div>
            <div className={styles.generateSub}>This may take more than 1 minute.</div>
          </div>
        </Popup>
      )}
      {generateStatus === 'error' && (
        <Popup>
          <div className={styles.generateOverlay}>
            <div className={styles.generateErrorIcon}>!</div>
            <div className={styles.generateTitle}>Something went wrong</div>
            <div className={styles.generateError}>{generateError}</div>
            <button
              type="button"
              className="btn-primary"
              style={{ width: '100%' }}
              onClick={handleGenerate}
            >
              Try again
            </button>
            <button
              type="button"
              className="btn-ghost"
              onClick={() => setGenerateStatus('idle')}
            >
              Cancel
            </button>
          </div>
        </Popup>
      )}
    </div>
  )
}
