import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useSession } from '../store/session.tsx'
import { debugLog } from '../utils/debug'
import styles from './PreviewPage.module.css'

function CheckIcon() {
  return (
    <svg viewBox="0 0 12 12" fill="none" width="10" height="10" aria-hidden="true">
      <path d="M2 6l3 3 5-5" stroke="#3B6D11" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

export default function PreviewPage() {
  const navigate = useNavigate()
  const { finalPage } = useSession()

  // Redirect if no generated page in session
  useEffect(() => {
    if (!finalPage) {
      debugLog('preview-page', 'redirect.no_final_page')
      navigate('/new', { replace: true })
      return
    }
    debugLog('preview-page', 'render.final_page_ready', { htmlLength: finalPage.html.length })
  }, [finalPage, navigate])

  if (!finalPage) return null

  return (
    <div>
      <nav className="top-nav">
        <span className="nav-logo">Landing Builder</span>
      </nav>

      <div className={styles.shell}>
        {/* In-page header */}
        <div className={styles.appHeader}>
          <div className={styles.badge}>
            <CheckIcon />
          </div>
          <span className={styles.headerTitle}>Final page</span>
        </div>

        {/* Preview area */}
        <div className={styles.previewArea}>
          <div className={styles.iframeContainer}>
            <iframe
              className={styles.iframe}
              srcDoc={finalPage.html}
              sandbox="allow-scripts"
              title="Landing page preview"
            />
          </div>
        </div>

        {/* Footer */}
        <div className={styles.footer}>
          <button
            type="button"
            className="btn-secondary"
            onClick={() => navigate('/review')}
          >
            Back to plan
          </button>
          <button
            type="button"
            className="btn-secondary"
            onClick={() => navigate('/new')}
          >
            Edit prompt
          </button>
        </div>
      </div>
    </div>
  )
}
