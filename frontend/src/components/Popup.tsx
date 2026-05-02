import { type ReactNode } from 'react'
import styles from './Popup.module.css'

interface Props {
  children: ReactNode
  /** If provided, clicking the backdrop dismisses the popup */
  onClose?: () => void
}

export default function Popup({ children, onClose }: Props) {
  function handleBackdrop(e: React.MouseEvent<HTMLDivElement>) {
    if (onClose && e.target === e.currentTarget) onClose()
  }

  return (
    <div className={styles.overlay} onClick={handleBackdrop}>
      <div className={styles.card}>
        {onClose && (
          <button
            type="button"
            className={styles.closeBtn}
            onClick={onClose}
            aria-label="Close popup"
          >
            ×
          </button>
        )}
        {children}
      </div>
    </div>
  )
}
