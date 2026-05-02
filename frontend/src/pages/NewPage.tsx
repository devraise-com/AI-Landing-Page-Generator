import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useSession } from '../store/session'
import { generatePlan } from '../api/client'
import { isApiError } from '../api/errors'
import { TONE_OPTIONS } from '../types/ui'
import Popup from '../components/Popup'
import { debugError, debugLog, debugWarn } from '../utils/debug'
import styles from './NewPage.module.css'

// ── Constants ─────────────────────────────────────────────────

const STEPS = [
  'Analyzing your product',
  'Defining page structure',
  'Writing section copy',
  'Generating visual directions',
]

const MIN_PROMPT_LEN = 20

// ── Error mapping ─────────────────────────────────────────────

function getErrorMessage(err: unknown): string {
  if (isApiError(err)) {
    if (err.status === 400) return err.message
    if (err.status === 401) return 'Access error — token is missing or invalid.'
    if (err.status === 429) return 'Rate limit reached. Please try again in a moment.'
    return err.message || 'Something went wrong. Please try again.'
  }
  return 'Network error. Please check your connection and try again.'
}

// ── Subcomponents ─────────────────────────────────────────────

function LoadingContent({ step }: { step: number }) {
  return (
    <>
      <div className={`spinner ${styles.popupSpinner}`} />
      <div className={styles.popupTitle}>Building your landing plan...</div>
      <div className={styles.stepList}>
        {STEPS.map((label, i) => {
          const done = i < step
          const prog = i === step
          return (
            <div
              key={i}
              className={`${styles.stepItem} ${!done && !prog ? styles.stepPending : ''}`}
            >
              <span className={`${styles.stepIc} ${done ? styles.stepIcDone : prog ? styles.stepIcProg : ''}`}>
                {done ? '✓' : prog ? '…' : '·'}
              </span>
              {label}
            </div>
          )
        })}
      </div>
    </>
  )
}

function ErrorContent({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <>
      <div className={styles.errorIcon}>!</div>
      <div className={styles.popupTitle}>Something went wrong</div>
      <p className={styles.errorText}>{message}</p>
      <button type="button" className="btn-primary" style={{ width: '100%' }} onClick={onRetry}>
        Try again
      </button>
    </>
  )
}

// ── Page ──────────────────────────────────────────────────────

type Status = 'idle' | 'loading' | 'error'

export default function NewPage() {
  const navigate = useNavigate()
  const { prompt, tone, setPrompt, setTone, setLandingPlan, setFinalPage } = useSession()

  // Local prompt mirrors session on mount, stays local until submit
  const [localPrompt, setLocalPrompt] = useState(prompt)
  const [status, setStatus] = useState<Status>('idle')
  const [errorMsg, setErrorMsg] = useState('')
  const [loadingStep, setLoadingStep] = useState(0)

  const timers = useRef<ReturnType<typeof setTimeout>[]>([])

  // Cleanup on unmount
  useEffect(() => {
    return () => timers.current.forEach(clearTimeout)
  }, [])

  async function submit() {
    const trimmed = localPrompt.trim()
    if (trimmed.length < MIN_PROMPT_LEN) {
      debugWarn('new-page', 'submit.blocked_min_length', {
        actualLength: trimmed.length,
        minLength: MIN_PROMPT_LEN,
      })
      return
    }

    debugLog('new-page', 'submit.start', {
      promptLength: trimmed.length,
      tone,
    })

    // Persist to session
    setPrompt(trimmed)
    // Clear any stale final page when starting fresh
    setFinalPage(null)

    // Start loading state + step animation
    setStatus('loading')
    setLoadingStep(0)
    timers.current.forEach(clearTimeout)
    timers.current = [
      setTimeout(() => setLoadingStep(1), 2800),
      setTimeout(() => setLoadingStep(2), 5600),
      setTimeout(() => setLoadingStep(3), 8400),
    ]

    try {
      const result = await generatePlan(trimmed, tone)
      debugLog('new-page', 'submit.success', {
        sectionsCount: result.sections.length,
      })
      timers.current.forEach(clearTimeout)
      setLandingPlan({ sections: result.sections })
      navigate('/review')
    } catch (err) {
      debugError('new-page', 'submit.failed', err)
      timers.current.forEach(clearTimeout)
      setStatus('error')
      setErrorMsg(getErrorMessage(err))
    }
  }

  const canSubmit = localPrompt.trim().length >= MIN_PROMPT_LEN

  return (
    <div className={styles.root}>
      {/* ── Content layer (blurs behind popup) ── */}
      <div className={`${styles.pageContent} ${status === 'loading' ? styles.blurred : ''}`}>
        <nav className="top-nav">
          <span className="nav-logo">Landing Builder</span>
        </nav>

        <div className={styles.page}>
          <div className={styles.inner}>
            {/* Left: title + description */}
            <div>
              <h1 className={styles.heading}>Describe your product</h1>
              <p className={styles.subheading}>
                We'll generate a complete landing page plan — structure, copy, and visual
                directions for each section.
              </p>
            </div>

            {/* Right: form */}
            <div className={styles.right}>
              <div className={styles.fieldGroup}>
                <label className={styles.fieldLabel}>What are you building a page for?</label>
                <textarea
                  className={styles.textarea}
                  placeholder={
                    'e.g. "A SaaS tool that helps freelancers send invoices in under 60 seconds — no templates, no spreadsheets"'
                  }
                  value={localPrompt}
                  onChange={e => setLocalPrompt(e.target.value)}
                  disabled={status === 'loading'}
                />
              </div>

              <div className={styles.fieldGroup}>
                <label className={styles.fieldLabel}>Tone</label>
                <div className={styles.toneRow}>
                  {TONE_OPTIONS.map(opt => (
                    <button
                      key={opt.value}
                      type="button"
                      className={`${styles.toneChip} ${tone === opt.value ? styles.toneChipActive : ''}`}
                      onClick={() => setTone(opt.value)}
                      disabled={status === 'loading'}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              </div>

              <button
                type="button"
                className={`btn-primary ${styles.submitBtn}`}
                onClick={submit}
                disabled={!canSubmit || status === 'loading'}
              >
                Generate landing plan
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
                  <path
                    d="M3 7h8M8 4l3 3-3 3"
                    stroke="#fff"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* ── Popup ── */}
      {status === 'loading' && (
        <Popup>
          <LoadingContent step={loadingStep} />
        </Popup>
      )}
      {status === 'error' && (
        <Popup onClose={() => setStatus('idle')}>
          <ErrorContent message={errorMsg} onRetry={submit} />
        </Popup>
      )}
    </div>
  )
}
