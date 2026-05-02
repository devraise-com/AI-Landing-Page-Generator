import type { Section } from '../types/api'
import styles from './PlanCard.module.css'

// ── Helpers ───────────────────────────────────────────────────

const PALETTE = ['#AFA9EC', '#5DCAA5', '#9FE1CB', '#7F77DD', '#F0D080', '#B8D4F0']

function swatchColor(type: string): string {
  let h = 0
  for (const c of type) h = (h * 31 + c.charCodeAt(0)) & 0xfff
  return PALETTE[h % PALETTE.length]
}

function tagClass(type: string): string {
  if (/hero|header|banner|above/.test(type)) return styles.tagPurple
  if (/feature|faq|benefit|why|social|proof/.test(type)) return styles.tagGreen
  return styles.tagTeal
}

function renderValue(raw: unknown): string {
  if (typeof raw === 'string') return raw
  if (typeof raw === 'number') return String(raw)
  if (Array.isArray(raw)) {
    return raw
      .slice(0, 4)
      .map(item => {
        if (typeof item === 'string') return item
        if (typeof item === 'object' && item !== null) {
          return Object.values(item as Record<string, unknown>)
            .filter(v => typeof v === 'string')
            .slice(0, 1)
            .join('')
        }
        return String(item)
      })
      .join(' · ')
  }
  if (typeof raw === 'object' && raw !== null) {
    return Object.values(raw as Record<string, unknown>)
      .filter(v => typeof v === 'string')
      .slice(0, 2)
      .join(' — ')
  }
  return String(raw)
}

function fieldLabel(key: string): string {
  return key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

// ── Icons ─────────────────────────────────────────────────────

function EditIcon() {
  return (
    <svg viewBox="0 0 14 14" fill="none" width="12" height="12" aria-hidden="true">
      <path d="M9.5 2.5l2 2L4 12H2v-2L9.5 2.5z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round" />
    </svg>
  )
}

function TrashIcon() {
  return (
    <svg viewBox="0 0 14 14" fill="none" width="12" height="12" aria-hidden="true">
      <path
        d="M2 4h10M5 4V3h4v1M5.5 6.5v4M8.5 6.5v4M3 4l.7 7.3A1 1 0 004.7 12h4.6a1 1 0 001-.9L11 4"
        stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"
      />
    </svg>
  )
}

// ── Component ─────────────────────────────────────────────────

interface Props {
  section: Section
  onEdit: () => void
  onDelete: () => void
  removing: boolean
}

export default function PlanCard({ section, onEdit, onDelete, removing }: Props) {
  const fieldEntries = Object.entries(section.fields).slice(0, 3)
  const color = swatchColor(section.type)

  return (
    <div className={`${styles.card} ${removing ? styles.removing : ''}`}>
      <div className={styles.head}>
        <div className={styles.headLeft}>
          <span className={styles.name}>{section.name}</span>
          <span className={`${styles.tag} ${tagClass(section.type)}`}>{section.type}</span>
        </div>
        <div className={styles.actions}>
          <button type="button" className={styles.iconBtn} onClick={onEdit} title="Edit section">
            <EditIcon />
          </button>
          <button type="button" className={styles.iconBtn} onClick={onDelete} title="Delete section">
            <TrashIcon />
          </button>
        </div>
      </div>

      <div className={styles.body}>
        {fieldEntries.map(([key, val]) => (
          <div key={key}>
            <div className={styles.fieldLbl}>{fieldLabel(key)}</div>
            <div className={styles.fieldVal}>{renderValue(val)}</div>
          </div>
        ))}
        {section.visual_direction && (
          <div>
            <div className={styles.fieldLbl}>Visual direction</div>
            <div className={styles.visHint}>
              <div className={styles.visSwatch} style={{ background: color }} />
              <div className={styles.visTxt}>{section.visual_direction}</div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
