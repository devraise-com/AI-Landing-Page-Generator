import { ApiError } from './errors'
import type { GeneratePlanResponse, GeneratePageResponse, LandingPlan, Section, Tone } from '../types/api'
import { debugError, debugLog, debugWarn } from '../utils/debug'

const BASE_URL = import.meta.env.VITE_API_URL
const TOKEN = import.meta.env.VITE_ANONYMOUS_TOKEN

if (!BASE_URL) throw new Error('VITE_API_URL is not set')
if (!TOKEN) throw new Error('VITE_ANONYMOUS_TOKEN is not set')

const authHeaders: Record<string, string> = {
  'Content-Type': 'application/json',
  'x-anonymous-token': TOKEN,
}

async function requestJson<T>(path: string, body: unknown): Promise<T> {
  const url = `${BASE_URL}${path}`
  debugLog('api', 'request.start', { path, url, body })

  const response = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    headers: authHeaders,
    body: JSON.stringify(body),
  })

  const contentType = response.headers.get('content-type') ?? ''
  const isJson = contentType.includes('application/json')
  debugLog('api', 'request.response', {
    path,
    status: response.status,
    ok: response.ok,
    contentType,
  })

  if (!response.ok) {
    if (isJson) {
      const payload = await response.json()
      debugWarn('api', 'request.error_json', { path, status: response.status, payload })
      throw new ApiError(response.status, payload)
    }
    const text = await response.text()
    debugWarn('api', 'request.error_text', { path, status: response.status, text })
    throw new ApiError(response.status, { error: text || `HTTP ${response.status}` })
  }

  try {
    const payload = await response.json()
    debugLog('api', 'request.success', { path, payload })
    return payload as T
  } catch (err) {
    debugError('api', 'response.json_parse_failed', { path, error: err })
    throw err
  }
}

export const generatePlan = (prompt: string, tone: Tone): Promise<GeneratePlanResponse> =>
  requestJson('/api/generate-plan', { prompt, tone })

export const parseSection = (
  sectionId: string,
  rawText: string,
  sectionType: string,
): Promise<Section> =>
  requestJson('/api/parse-section', { sectionId, rawText, sectionType })

export const generatePage = (landingPlan: LandingPlan): Promise<GeneratePageResponse> =>
  requestJson('/api/generate-page', { landingPlan })
