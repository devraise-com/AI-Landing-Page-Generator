import type { Tone } from './api'

export interface ToneOption {
  value: Tone
  label: string
}

export const TONE_OPTIONS: ToneOption[] = [
  { value: 'professional', label: 'Professional' },
  { value: 'friendly',     label: 'Friendly' },
  { value: 'bold',         label: 'Bold' },
  { value: 'minimal',      label: 'Minimal' },
]

// Review page view state
export type ReviewView = 'list' | 'edit'
