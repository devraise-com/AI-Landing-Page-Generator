export type Tone = 'professional' | 'friendly' | 'bold' | 'minimal'

export interface Section {
  id: string
  name: string
  type: string
  fields: Record<string, unknown>
  visual_direction: string
}

export interface LandingPlan {
  sections: Section[]
}

export interface FinalPage {
  html: string
}

export interface GeneratePlanResponse {
  sections: Section[]
}

export interface GeneratePageResponse {
  html: string
}
