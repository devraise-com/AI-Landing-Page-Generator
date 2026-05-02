import {
  createContext,
  useContext,
  useState,
  useCallback,
  type ReactNode,
} from 'react'
import type { LandingPlan, FinalPage, Tone } from '../types/api'

// ── Storage keys ──────────────────────────────────────────────
const KEY_PROMPT       = 'prompt'
const KEY_TONE         = 'tone'
const KEY_LANDING_PLAN = 'landingPlan'
const KEY_FINAL_PAGE   = 'finalPage'

function readJson<T>(key: string): T | null {
  try {
    const raw = sessionStorage.getItem(key)
    return raw ? (JSON.parse(raw) as T) : null
  } catch {
    return null
  }
}

function writeJson(key: string, value: unknown): void {
  try {
    sessionStorage.setItem(key, JSON.stringify(value))
  } catch {
    // sessionStorage unavailable — silently skip
  }
}

function remove(key: string): void {
  try {
    sessionStorage.removeItem(key)
  } catch {
    // ignore
  }
}

// ── Context shape ─────────────────────────────────────────────
interface SessionState {
  prompt: string
  tone: Tone
  landingPlan: LandingPlan | null
  finalPage: FinalPage | null
}

interface SessionActions {
  setPrompt: (v: string) => void
  setTone: (v: Tone) => void
  setLandingPlan: (v: LandingPlan | null) => void
  setFinalPage: (v: FinalPage | null) => void
  clearAll: () => void
}

type SessionContextValue = SessionState & SessionActions

const SessionContext = createContext<SessionContextValue | null>(null)

// ── Provider ──────────────────────────────────────────────────
function SessionProvider({ children }: { children: ReactNode }) {
  const [prompt, setPromptState] = useState<string>(
    () => readJson<string>(KEY_PROMPT) ?? '',
  )
  const [tone, setToneState] = useState<Tone>(
    () => readJson<Tone>(KEY_TONE) ?? 'professional',
  )
  const [landingPlan, setLandingPlanState] = useState<LandingPlan | null>(
    () => readJson<LandingPlan>(KEY_LANDING_PLAN),
  )
  const [finalPage, setFinalPageState] = useState<FinalPage | null>(
    () => readJson<FinalPage>(KEY_FINAL_PAGE),
  )

  const setPrompt = useCallback((v: string) => {
    setPromptState(v)
    writeJson(KEY_PROMPT, v)
  }, [])

  const setTone = useCallback((v: Tone) => {
    setToneState(v)
    writeJson(KEY_TONE, v)
  }, [])

  const setLandingPlan = useCallback((v: LandingPlan | null) => {
    setLandingPlanState(v)
    if (v === null) remove(KEY_LANDING_PLAN)
    else writeJson(KEY_LANDING_PLAN, v)
  }, [])

  const setFinalPage = useCallback((v: FinalPage | null) => {
    setFinalPageState(v)
    if (v === null) remove(KEY_FINAL_PAGE)
    else writeJson(KEY_FINAL_PAGE, v)
  }, [])

  const clearAll = useCallback(() => {
    setPromptState('')
    setToneState('professional')
    setLandingPlanState(null)
    setFinalPageState(null)
    ;[KEY_PROMPT, KEY_TONE, KEY_LANDING_PLAN, KEY_FINAL_PAGE].forEach(remove)
  }, [])

  return (
    <SessionContext.Provider
      value={{
        prompt, tone, landingPlan, finalPage,
        setPrompt, setTone, setLandingPlan, setFinalPage, clearAll,
      }}
    >
      {children}
    </SessionContext.Provider>
  )
}

// ── Hook ──────────────────────────────────────────────────────
function useSession(): SessionContextValue {
  const ctx = useContext(SessionContext)
  if (!ctx) throw new Error('useSession must be used inside SessionProvider')
  return ctx
}

// eslint-disable-next-line react-refresh/only-export-components
export { SessionProvider, useSession }
