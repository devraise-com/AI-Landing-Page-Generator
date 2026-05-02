const DEBUG_FLAG = import.meta.env.VITE_DEBUG_LOGS

function isEnabled(): boolean {
  if (typeof DEBUG_FLAG !== 'string') return false
  return ['1', 'true', 'yes', 'on'].includes(DEBUG_FLAG.toLowerCase())
}

export function debugLog(scope: string, message: string, data?: unknown): void {
  if (!isEnabled()) return
  if (data === undefined) {
    console.info(`[${scope}] ${message}`)
    return
  }
  console.info(`[${scope}] ${message}`, data)
}

export function debugWarn(scope: string, message: string, data?: unknown): void {
  if (!isEnabled()) return
  if (data === undefined) {
    console.warn(`[${scope}] ${message}`)
    return
  }
  console.warn(`[${scope}] ${message}`, data)
}

export function debugError(scope: string, message: string, data?: unknown): void {
  if (!isEnabled()) return
  if (data === undefined) {
    console.error(`[${scope}] ${message}`)
    return
  }
  console.error(`[${scope}] ${message}`, data)
}

